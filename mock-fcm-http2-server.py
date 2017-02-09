import collections
import http
import time
import uuid
import random

import flask

app = flask.Flask(__name__)

KEY_AUTH_ID = 'authorization'
KEY_DEVICE_TOKEN = 'device_token'
KEY_STATUS = 'status'
KEY_REASON = 'reason'
KEY_TIMESTAMP = 'timestamp'


ErrorConfig = collections.namedtuple(
    'ErrorConfig',
    [KEY_STATUS, KEY_REASON, KEY_TIMESTAMP]
)

# Maps device token to ErrorConfig
ERRORS_TO_RETURN = {}


ACTIVITY_RECORD_FIELDS = [
    'device_token',
    'request_headers',
    'request_data',
    'response_status',
    'response_data'
]
ActivityRecord = collections.namedtuple(
    'ActivityRecord',
    ACTIVITY_RECORD_FIELDS
)


# Records activity
ACTIVITY = []


@app.route('/error-tokens', methods=('POST', 'PUT', 'GET'))
def error_tokens():
    """
    POST or PUT that gives us a set of tokens to which we should
    return specific response. A GET returns the current setup.
    """
    if flask.request.method in ('POST', 'PUT'):
        configuration = flask.request.get_json(force=True, silent=True)
        if not configuration:
            return http.HTTPStatus.BAD_REQUEST, 'No (or empty) JSON data found'

        if not isinstance(configuration, list):
            return http.HTTPStatus.BAD_REQUEST, 'Expected a list'

        for config in configuration:
            # We expect subscription_id, status, reason and optional timestamp
            try:
                subscription_id = config[KEY_DEVICE_TOKEN]
                status = config[KEY_STATUS]
                reason = config[KEY_REASON]
                timestamp = config.get(KEY_TIMESTAMP)

            except KeyError as ex:
                return http.HTTPStatus.BAD_REQUEST, 'Missing key {}'.format(ex)

            ERRORS_TO_RETURN[subscription_id] = ErrorConfig(
                status, reason, timestamp
            )

    return flask.jsonify(ERRORS_TO_RETURN)


@app.route('/reset', methods=('POST', 'PUT'))
def reset():
    """
    Reset the test server status
    """
    ERRORS_TO_RETURN.clear()
    ACTIVITY.clear()

    return 'OK'


# The main mocked endpoint
@app.route('/fcm/send', methods=['POST'])
def push_to_device():
    auth_key = flask.request.headers.get(KEY_AUTH_ID)
    if auth_key is None:
        response = flask.make_response(
            '',
            http.HTTPStatus.UNAUTHORIZED
        )
        return response

    request_data = flask.request.get_json(force=True, silent=False)
    print(request_data)
    if request_data['to'] is not None:
        device_tokens = [request_data['to']]
    else:
        device_tokens = request_data['registration_ids']

    results = []
    success = 0
    failure = 0
    for device_token in device_tokens:
        print('push_to_device(\'{}\''.format(device_token))

        error = ERRORS_TO_RETURN.get(device_token)
        if error is None:
            success += 1
            results.append({'message_id': "23hrjniofwc0923hno"})
        else:
            failure += 1
            results.append({'error': error.reason})

        response_data = {
            'multicast_id': random.uniform(1000, 99999999),
            'success': success,
            'failure': failure,
            'canonical_ids': 0,
            'results': results
        }
        response = flask.jsonify(response_data)
        response.status_code = 200

        ACTIVITY.append(
            ActivityRecord(
                device_token,
                # Must convert the headers to a simple dict with
                # consistent key case.
                dict(
                    (key.lower(), str(value))
                    for key, value in flask.request.headers.items()
                ),
                request_data,
                response.status_code,
                response_data
            )
        )
    return response


@app.route('/activity')
def activity():
    """
    Return a JSON dump of activity
    """
    return flask.jsonify(
        dict(
            logs=[
                dict(
                    zip(ACTIVITY_RECORD_FIELDS, activity)
                )
                for activity in ACTIVITY
            ]
        )
    )


@app.before_request
def before_request():
    print(
        '{}, {}'.format(
            flask.request.method,
            flask.request.url,
        )
    )
