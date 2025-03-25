import os
import re
import json
import sys
import codecs
from gql.transport.aiohttp import AIOHTTPTransport
from gql import gql, Client
from datetime import datetime, timedelta
from google.cloud import datastore
from google.oauth2 import service_account
from google.cloud import storage
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange
from google.analytics.data_v1beta.types import Dimension
from google.analytics.data_v1beta.types import Metric
from google.analytics.data_v1beta.types import RunReportRequest
from datetime import datetime

def get_article(article_ids, extra=''):
    GQL_ENDPOINT = os.environ['GQL_ENDPOINT']
    gql_transport = AIOHTTPTransport(url=GQL_ENDPOINT)
    gql_client = Client(transport=gql_transport,
                        fetch_schema_from_transport=False)
    report = []
    popular = {}
    rows = 0
    for article in article_ids:
        #writer.writerow([row.dimension_values[0].value, row.dimension_values[1].value.encode('utf-8'), row.metric_values[0].value])
        uri = article.dimension_values[1].value
        id_match = re.match('/story/(\w+)', uri)
        if id_match:
            post_id = id_match.group(1)
            if post_id:
                post_gql = '''
                    query{
                        post(where:{id:"%s"}){
                            id
                            slug
                            sections{id, name, slug, state}
                            sectionsInInputOrder{id, name, slug, state}
                            title
                            style
                            state
                            publishedDate
                            heroImage{
                                id, 
                                resized{
                                    original
                                    w480,
                                    w800,
                                    w1200,
                                    w1600,
                                    w2400
                                }
                                resizedWebp{
                                    original
                                    w480,
                                    w800,
                                    w1200,
                                    w1600,
                                    w2400
                                }
                            }
                            %s
                        }
                    }''' % (post_id, extra)
                query = gql(post_gql)
                post = gql_client.execute(query)
                if isinstance(post, dict) and 'post' in post and post['post'] is not None and post['post']['state'] == 'published' and post['post']['id'] not in popular:
                    # Avoid the dulplicate article
                    popular[post['post']['id']] = 1
                    # Append post to report
                    rows += 1
                    report.append(post['post'])
        if rows > 20:
            break
        #report.append({'title': row.dimension_values[0].value, 'uri': row.dimension_values[1].value, 'count': row.metric_values[0].value})
    return report

def popular_report(property_id, dest_file='popular.json', extra='', ga_days: int=2):
    """Runs a simple report on a Google Analytics 4 property."""
    # TODO(developer): Uncomment this variable and replace with your
    #  Google Analytics 4 property ID before running the sample.
    # property_id = "311149968"

    # Using a default constructor instructs the client to use the credentials
    # specified in GOOGLE_APPLICATION_CREDENTIALS environment variable.
    if sys.stdout:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    client = BetaAnalyticsDataClient()

    current_time = datetime.now()
    start_datetime = current_time - timedelta(days=ga_days)
    start_date = datetime.strftime(start_datetime, '%Y-%m-%d')

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[
		    Dimension(name="pageTitle"),
		    Dimension(name="pagePath")
		],
        metrics=[Metric(name="screenPageViews")],
        date_ranges=[DateRange(start_date=start_date, end_date="today")],
    )
    response = client.run_report(request)
    print("report result")
    print(response)

    report = get_article(response.rows, extra)
    gcs_path = os.environ['GCS_PATH']
    bucket = os.environ['BUCKET']
    upload_data(bucket, json.dumps(report, ensure_ascii=False).encode('utf8'), 'application/json', gcs_path + dest_file)
    return "Ok"

def recent_popular_report(property_id, dest_file='popular.json', days: int=1):
    # env and config
    POPULAR_POSTS_NUM = 30
    GQL_ENDPOINT = os.environ['GQL_ENDPOINT']
    gcs_path = os.environ['GCS_PATH']
    bucket   = os.environ['BUCKET']
    
    # get recent posts
    if sys.stdout:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    current_time = datetime.now()
    start_datetime = (current_time - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    filter_publishedDate = f"\"{start_datetime.isoformat(timespec='seconds')}Z\""
    
    
    gql_transport = AIOHTTPTransport(url=GQL_ENDPOINT)
    gql_client = Client(transport=gql_transport,
                        fetch_schema_from_transport=False)
    posts_gql = '''
        query{{
            posts(where: {{publishedDate: {{gt: {START_DATE} }} }}){{
                id
                slug
                sections{{id, name, slug, state}}
                sectionsInInputOrder{{id, name, slug, state}}
                title
                style
                state
                publishedDate
                heroImage{{
                    id, 
                    resized{{
                        original
                        w480,
                        w800,
                        w1200,
                        w1600,
                        w2400
                    }},
                    resizedWebp{{
                        original
                        w480,
                        w800,
                        w1200,
                        w1600,
                        w2400
                    }}
                }}
            }}
        }}
    '''.format(START_DATE=filter_publishedDate)
    data = gql_client.execute(gql(posts_gql))
    
    # organize posts
    posts = data['posts']
    posts_table = {
        f"/story/{post['slug']}": post for post in posts
    }
    filter_slugs = list(posts_table.keys())
    
    # fetch ga-analytics data
    start_date = datetime.strftime(start_datetime, '%Y-%m-%d')
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[
            Dimension(name="pagePath")
        ],
        metrics=[Metric(name="screenPageViews")],
        date_ranges=[DateRange(start_date=start_date, end_date="today")],
        dimension_filter={
            "filter": {
                "field_name": "pagePath",
                "in_list_filter": {
                    "values": filter_slugs,
                }
            }
        }
    )
    client = BetaAnalyticsDataClient()
    response = client.run_report(request)
    
    # organize result
    rows = response.rows
    statistic_data = {row.dimension_values[0].value: int(row.metric_values[0].value) for row in rows}
    sorted_statistic_data = sorted(statistic_data.items(), key=lambda item: item[1], reverse=True)[:POPULAR_POSTS_NUM]
    
    report = []
    for data in sorted_statistic_data:
        slug = data[0]
        post = posts_table[slug]
        report.append(post)
    
    # upload
    upload_data(bucket, json.dumps(report, ensure_ascii=False).encode('utf8'), 'application/json', gcs_path + dest_file)
    return "ok"

def upload_data(bucket_name: str, data: str, content_type: str, destination_blob_name: str):
    '''Uploads a file to the bucket.'''
    # bucket_name = 'your-bucket-name'
    # data = 'storage-object-content'
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    # blob.content_encoding = 'gzip'
    blob.upload_from_string(
        # data=gzip.compress(data=data, compresslevel=9),
        data=bytes(data),
        content_type=content_type, client=storage_client)
    blob.content_language = 'zh'
    blob.cache_control = 'max-age=300,public'
    blob.patch()

if __name__ == "__main__":  
	if 'GA_RESOURCE_ID' in os.environ:
		ga_id = os.environ['GA_RESOURCE_ID']
	else:
		ga_id = "311149968"
	popular_report(ga_id)
