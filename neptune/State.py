import pickle
import requests


class State(dict):

    def __init__(self, game_id, cookies):
        dict.__init__(self,
                      game_id=game_id,
                      cookies=cookies)

    @staticmethod
    def new(login, password, credentials, game_id):
        if login:
            cookies = State.login(login, password)
            state = State(game_id, cookies)
            state.save(credentials)
        else:
            state = State.load(credentials)
        return state

    @staticmethod
    def login(login, password):
        print("Logging in with email/password")
        cookies = requests.post(
            'https://np.ironhelmet.com/arequest/login',
            data={'type': 'login',
                  'alias': login,
                  'password': password}).cookies
        return cookies

    @staticmethod
    def load(credentials):
        """
        Read state from a file
        """
        with open(credentials, 'rb') as creds:
            state = pickle.load(creds)
            print(f"Read state from {credentials}: game_id={state['game_id']}")
            return state

    def save(self, credentials):
        """
        Write state to a file
        :param credentials:
        :return:
        """
        with open(credentials, "wb") as creds:
            pickle.dump(self, creds)
            print("Wrote cookies to %s" % credentials)

