import json
import os
import requests
import sys
import time

from neptune.Fleets import Fleets
from neptune.Players import Players
from neptune.Stars import Stars


class Universe(object):
    UNIVERSE_FILE = "universe.json"

    def __init__(self, data, state):
        self.data = data
        self.state = state

        if 'player_uid' not in self.data['report']:
            print(f"get_universe(): invalid universe: {json.dumps(self.data)}")
            sys.exit()

        # Parse objects from the data
        self.fleets = Fleets.from_universe(self)
        self.stars = Stars.from_universe(self)
        self.players = Players.from_universe(self)

        # Calculate the beginning time of the next tick
        seconds_to_tick = (self.data["report"]['tick_rate'] -
                              self.data["report"]['tick_fragment'] *
                              self.data["report"]['tick_rate']) * 60
        self.tick_time = time.time() + seconds_to_tick

    @staticmethod
    def get_universe(use_file, state):
        if use_file and os.path.isfile(Universe.UNIVERSE_FILE):
            with open(Universe.UNIVERSE_FILE, "r") as fd:
                universe = Universe(json.load(fd), state)
                print(f"get_universe(): read universe from {Universe.UNIVERSE_FILE}")
        else:
            print("get_universe(): querying for universe")
            response = requests.post('https://np.ironhelmet.com/trequest/order',
                                     data={'type': 'order',
                                           'order': 'full_universe_report',
                                           'version': '',
                                           'game_number': state["game_id"]},
                                     cookies=state["cookies"])
            if response.status_code != requests.codes.ok:
                print(f"get_universe(): request failed, code {response.status_code}")
                print("  data: %s" % response.text)
                sys.exit(1)
            universe = Universe(response.json(), state)

            # Save the universe to file
            with open(Universe.UNIVERSE_FILE, "w") as f:
                f.write(json.dumps(universe.data))

        return universe

    def player(self):
        """
        :return: The logged in player
        """
        player_id = self.data['report']['player_uid']
        return self.players.by_id(player_id)

    def cash(self):
        """
        :return: The current cash of the logged in player
        """
        return self.data['report']['players'][str(self.player()['id'])]['cash']

    def seconds_to_tick(self):
        """
        :return: Seconds until the next tick
        """
        return self.tick_time - time.time()
