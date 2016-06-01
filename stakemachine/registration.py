from graphenebase import account
import requests
import json


faucet = "https://bitshares.openledger.info/"
referrer = "xeroc"


def register_account_faucet(account, public_key, referrer = referrer, faucet = faucet):
    headers = {
                "Accept": "application/json",
                "Content-type": "application/json",
                "User-Agent": "stakemachine/0.5"
    }
    payload = {
                "account": {
                "name": account,
                "owner_key": public_key,
                "active_key": public_key,
                "memo_key": public_key,
                "refcode": referrer,
                "referrer": referrer
        }
    }
    request = requests.post(faucet + '/api/v1/accounts', data=json.dumps(payload), headers=headers)
    return (request.status_code == 201, request.text)


def register_account(account_name, wif_key=None):
    if not wif_key:
        brainKey = account.BrainKey()
        privateKey = brainKey.get_private()
    else:
        privateKey = account.PrivateKey(wif_key)

    publicKey = privateKey.pubkey
    public_key = format(publicKey, "BTS")
    account_registered, account_registration_response = register_account_faucet(account_name, public_key)
    if account_registered:
        if not wif_key:
            print("Brain key: %s" % brainKey.get_brainkey())
            print("Write it down/back it up ^")
        print("Account: %s successfully registered" % account_name)
        print("WIF key add this to config.yml: %s" % format(privateKey, "WIF"))
        print("Send funds to %s and start the bot again" % account_name)
        return format(privateKey, "WIF")
    else:
        print("Account creation failed")
        if not wif_key:
            print(brainKey.get_brainkey())
        print(faucet + " response: ", account_registration_response)
        return None


if __name__ == '__main__':
    account_name = input("Enter the account name to register: ")
    print("Trying to register %s..." % account_name)
    register_account(account_name)
