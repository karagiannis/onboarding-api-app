from flask import Flask, request, jsonify, render_template_string
import configparser
import urllib.parse
import requests
import stripe

app = Flask(__name__)

# Läs konfigurationsvärden från config.ini
config = configparser.ConfigParser()
config.read('config.ini')
CLIENT_ID = config['Tink']['client_id']
CLIENT_SECRET = config['Tink']['client_secret']
STRIPE_SECRET_KEY = config['Stripe']['secret_key']
STRIPE_PUBLIC_KEY = config['Stripe']['public_key']

# Initiera Stripe
stripe.api_key = STRIPE_SECRET_KEY

# --- TINK DEL ---
@app.route('/')
def index():
    html = '''
    <h1>Välkommen till Onboarding-appen</h1>
    <p><a href="/start-business-check">Testa Tink (Bankdata)</a></p>
    <p><a href="/pay-3-kr">Testa betalning (3 kr)</a></p>
    <p><a href="/subscribe">Teckna prenumeration (40 kr/mån)</a></p>
    '''
    return html

@app.route('/start-business-check')
def start_business_check():
    market = request.args.get('market', 'DE')
    locale = request.args.get('locale', 'sv_SE')
    redirect_uri = 'https://celestial.se/callback'
    input_provider = request.args.get('input_provider', 'de-demobank-password')

    base_url = 'https://link.tink.com/1.0/business-account-check/create-report/'
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': redirect_uri,
        'market': market,
        'locale': locale,
        'input_provider': input_provider
    }
    url = base_url + '?' + urllib.parse.urlencode(params)
    return f'<a href="{url}" target="_blank">Starta Business Account Check för {market} med provider {input_provider}</a>'

@app.route('/callback')
def callback():
    print(">>> Callback mottagen från Tink!")
    auth_code = request.args.get('code')
    error = request.args.get('error')
    print(f">>> Query parameters - auth_code: {auth_code}, error: {error}")

    if error:
        print(f">>> Fel vid Tink-autentisering: {error}")
        return f'Fel vid Tink-autentisering: {error}'

    if auth_code:
        print(">>> Auth code mottagen, försöker byta till access token...")
        token_url = 'https://api.tink.com/api/v1/oauth/token'
        payload = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': auth_code
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        response = requests.post(token_url, data=payload, headers=headers)
        print(f">>> Token endpoint svarade med status: {response.status_code}")
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            refresh_token = token_data.get('refresh_token')
            print(f">>> Access token mottagen: {access_token}")
            print(f">>> Refresh token mottagen: {refresh_token}")
            return (f'Access token mottagen: {access_token}<br>'
                    f'Refresh token: {refresh_token}')
        else:
            print(f">>> Fel vid token-utbyte: {response.status_code}, {response.text}")
            return f'Fel vid token-utbyte: {response.status_code}, {response.text}'

    print(">>> Callback mottagen utan auth code eller fel.")
    return 'Callback mottagen utan auth code eller fel.'

# --- STRIPE DEL ---

@app.route('/pay-3-kr')
def pay_3_kr():
    return render_template_string('''
    <h2>Testa betalning (3 kr)</h2>
    <button id="pay-button">Betala 3 kr</button>
    <script src="https://js.stripe.com/v3/"></script>
    <script>
      var stripe = Stripe('{{public_key}}');
      var button = document.getElementById('pay-button');
      button.addEventListener('click', function() {
        fetch('/create-payment-intent', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
        })
        .then(function(response) {
          return response.json();
        })
        .then(function(data) {
          stripe.confirmCardPayment(data.client_secret).then(function(result) {
            if (result.error) {
              alert(result.error.message);
            } else {
              alert('Betalning genomförd!');
            }
          });
        });
      });
    </script>
    ''', public_key=STRIPE_PUBLIC_KEY)

@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    try:
        intent = stripe.PaymentIntent.create(
            amount=300,  # 300 öre = 3 kr
            currency='sek',
        )
        return jsonify({'client_secret': intent['client_secret']})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/subscribe')
def subscribe():
    return render_template_string('''
    <h2>Teckna prenumeration (40 kr/mån)</h2>
    <button id="subscribe-button">Teckna prenumeration</button>
    <script src="https://js.stripe.com/v3/"></script>
    <script>
      var stripe = Stripe('{{public_key}}');
      var button = document.getElementById('subscribe-button');
      button.addEventListener('click', function() {
        fetch('/create-checkout-session', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
        })
        .then(function(response) {
          return response.json();
        })
        .then(function(data) {
          stripe.redirectToCheckout({sessionId: data.id});
        });
      });
    </script>
    ''', public_key=STRIPE_PUBLIC_KEY)

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'sek',
                    'product_data': {
                        'name': 'Onboarding App - Månadsavgift',
                    },
                    'unit_amount': 4000,  # 4000 öre = 40 kr
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url='https://celestial.se/success',
            cancel_url='https://celestial.se/cancel',
        )
        return jsonify({'id': session.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/success')
def success():
    return '<h2>Tack för din prenumeration!</h2>'

@app.route('/cancel')
def cancel():
    return '<h2>Prenumeration avbruten.</h2>'

if __name__ == '__main__':
    app.run(debug=True, port=3000)