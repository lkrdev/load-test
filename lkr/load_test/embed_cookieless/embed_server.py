
import os
from flask import Flask, request, session, render_template, jsonify
import looker_sdk
from looker_sdk import models40

from lkr.load_test.utils import (
    MAX_SESSION_LENGTH,
    PERMISSIONS,
    format_attributes,
    get_user_id,
)

app = Flask(__name__, template_folder='lkr/load_test/embed_cookieless')
app.secret_key = os.urandom(24)

# Initialize Looker SDK
sdk = looker_sdk.init40()

@app.route('/')
def embed_page():
    dashboard_id = request.args.get('dashboard_id', '1')
    return render_template('embed_container.html', looker_host=os.environ.get("LOOKERSDK_BASE_URL"), dashboard_id=dashboard_id)

@app.route('/acquire-embed-session', methods=['GET'])
def acquire_embed_session():
    user_id = get_user_id()
    attributes = format_attributes(["locale:en_US"])
    
    sso_user = models40.EmbedSsoParams(
        first_name="Cookieless Embed ",
        last_name=user_id,
        external_user_id=user_id,
        session_length=MAX_SESSION_LENGTH,
        target_url=f"{os.environ.get('LOOKERSDK_BASE_URL')}/embed/dashboards/{request.args.get('dashboard_id', '1')}",
        permissions=PERMISSIONS,
        models=["looker_test"],
        user_attributes=attributes,
        group_ids=["5"],
        external_group_id="test_group_1"
    )

    try:
        current_session_reference_token = session.get('session_reference_token')
        
        request_body = {
            **sso_user.to_dict(),
            "session_reference_token": current_session_reference_token,
        }

        response = sdk.acquire_embed_cookieless_session(
            body=request_body,
            headers={'User-Agent': request.user_agent.string}
        )
        
        session['session_reference_token'] = response.session_reference_token
        
        return jsonify({
            'api_token': response.api_token,
            'api_token_ttl': response.api_token_ttl,
            'authentication_token': response.authentication_token,
            'authentication_token_ttl': response.authentication_token_ttl,
            'navigation_token': response.navigation_token,
            'navigation_token_ttl': response.navigation_token_ttl,
            'session_reference_token_ttl': response.session_reference_token_ttl,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-embed-tokens', methods=['PUT'])
def generate_embed_tokens():
    try:
        session_reference_token = session.get('session_reference_token')
        if not session_reference_token:
            return jsonify({'error': 'Session not found'}), 404
            
        data = request.get_json()
        api_token = data.get('api_token')
        navigation_token = data.get('navigation_token')

        response = sdk.generate_tokens_for_cookieless_session(
            body={
                "session_reference_token": session_reference_token,
                "api_token": api_token,
                "navigation_token": navigation_token,
            },
            headers={'User-Agent': request.user_agent.string}
        )
        
        return jsonify({
            'api_token': response.api_token,
            'api_token_ttl': response.api_token_ttl,
            'navigation_token': response.navigation_token,
            'navigation_token_ttl': response.navigation_token_ttl,
            'session_reference_token_ttl': response.session_reference_token_ttl,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=8080)
