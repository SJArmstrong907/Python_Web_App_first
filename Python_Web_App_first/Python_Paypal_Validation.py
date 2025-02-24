from paypalrestsdk import WebhookEvent

@app.route('/paypal/webhook', methods=['POST'])
def paypal_webhook():
    webhook_id = "YOUR-WEBHOOK-ID"  # Found in your PayPal Developer Dashboard
    webhook_event = request.json

    # Verify the event
    try:
        response = WebhookEvent.verify(
            transmission_id=request.headers['Paypal-Transmission-Id'],
            timestamp=request.headers['Paypal-Transmission-Time'],
            webhook_id=webhook_id,
            event_body=json.dumps(webhook_event),
            cert_url=request.headers['Paypal-Cert-Url'],
            actual_signature=request.headers['Paypal-Transmission-Sig'],
            auth_algo=request.headers['Paypal-Auth-Algo']
        )
        if response['verification_status'] == 'SUCCESS':
            # Process the event as shown above
            pass
        else:
            app.logger.warning("Failed to verify PayPal webhook event")
            return jsonify({'status': 'failure', 'message': 'Invalid event'}), 400
    except Exception as e:
        app.logger.error(f"Error verifying webhook event: {e}")
        return jsonify({'status': 'error', 'message': 'Verification failed'}), 500
