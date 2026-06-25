import requests

resp = requests.post(
    "https://public-api.wordpress.com/oauth2/token",
    data={
        "client_id": "142632",
        "client_secret": "3VUIzQ0LtdCBrFYjFx16YJyPb6Yw486IjgiwTshHIdN9BKrgLiXAeW35NghvdRDr",
        "redirect_uri": "https://diakofart.github.io/manjubinha-analises/callback.html",
        "code": "Dk4EG9T1St&state",
        "grant_type": "authorization_code"
    }
)
print(resp.json())
