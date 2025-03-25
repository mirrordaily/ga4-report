from flask import Flask, request, jsonify
from ga_report import popular_report, recent_popular_report
import os
import json

app = Flask(__name__)

def check_extra_field_in_allowed_list(extra_field):
    check_result = {
        'status': 'success',
        'message': ''
    }
    
    if len(extra_field) == 0:
        check_result['status'] = 'success'
        check_result['message'] = 'Value of query `extra_field=` is not existed, generate popular list without extra_field'
    
    
    elif 'ALLOWED_EXTRA_FIELD' in os.environ and os.environ['ALLOWED_EXTRA_FIELD']:
            try:
                allowed_list = json.loads(os.environ['ALLOWED_EXTRA_FIELD'])
                is_list_type = isinstance(allowed_list, list)
                if is_list_type:
                    if extra_field in allowed_list:
                        check_result['status'] = 'success'
                        check_result['message'] = f'Valid value of query `extra_field`, generate popular list with query `extra_field={extra_field}`'
                    else:
                        check_result['status'] = 'fail'
                        check_result['message'] = f'Invalid value of query `extra_field`, please check extra_field {extra_field} is in allowed list'
                else:
                    check_result['status'] = 'fail'
                    check_result['message'] = 'Environment variable `ALLOWED_EXTRA_FIELD` should be a list, please check `ALLOWED_EXTRA_FIELD`'

            except json.decoder.JSONDecodeError as e:
                check_result['status'] = 'fail'
                check_result['message'] = f'Error occurred when decoding env variable `ALLOWED_EXTRA_FIELD`: {str(e)}'
                
            except Exception as e:
                check_result['status'] = 'fail'
                check_result['message'] = str(e)
    else:
        check_result['status'] = 'fail'
        check_result['message'] = f'`ALLOWED_EXTRA_FIELD` is not in environment variables or is empty, please check.'
 
    return check_result


@app.route("/generate_popular_report")
def generate_popular_report():
    '''
        Old implementation of popular report
    '''
    
    dest_file = request.args.get('dest_file', 'popular.json')
    post_number = request.args.get('post_number', 10)
    extra_field = request.args.get('extra_field','')
    ga_id = os.environ.get('GA_RESOURCE_ID', "311149968")
    ga_days = int(request.args.get('ga_days', '2'))
    # Check has allowed list of extra field.
    # If has, that value of extra_field must contain in env 'ALLOW_EXTRA_FIELD' to generate popular report        
    check_result = check_extra_field_in_allowed_list(extra_field)
    
    if check_result['status'] == 'success':
        popular_report(ga_id, dest_file, extra_field, ga_days, post_number)

    return jsonify(check_result)

@app.route("/recent_popular_report")
def generate_recent_popular_report():
    if request.args.get('dest_file'):
        dest_file = request.args.get('dest_file')
    else:
        dest_file = 'popular.json'
    if 'GA_RESOURCE_ID' in os.environ:
        ga_id = os.environ['GA_RESOURCE_ID']
    else:
        ga_id = "311149968"

    recent_popular_report(ga_id, dest_file, days=1)
    return jsonify({
        'status': 'success',
        'message': ''
    })

if __name__ == "__main__":
    app.run()
