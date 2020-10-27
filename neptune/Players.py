import json
import os
import sys

from neptune.Player import Player


class Players(dict):
    PLAYERS_FILE = "players.json"

    def __init__(self, players, universe):
        dict.__init__(self, players=players)
        self.universe = universe

    def update_from_file(self, filename):
        if not os.path.isfile(filename):
            print(f"No players config '{filename}'", file=sys.stderr)
            return
        with open(Players.PLAYERS_FILE, "r") as fd:
            players = json.load(fd)
            for p in players['players']:
                found = self.by_name(p['name'])
                found['state'] = p['state']

    @staticmethod
    def from_universe(universe):
        """Return an array of players from the universe"""
        global players

        player_array = []
        for player_id, player in universe.data['report']['players'].items():
            p = Player(player)
            if p['id'] == int(universe.data['report']['player_uid']):
                p['state'] = Player.SELF
            player_array.append(p)
        players = Players(sorted(player_array, key=lambda i: i['id']), universe)

        players.update_from_file(Players.PLAYERS_FILE)

        players.to_file(Players.PLAYERS_FILE)

        return players

    def to_file(self, filename):
        with open(filename, "w") as fd:
            json.dump(self, fd, indent=2, sort_keys=True)

    def by_name(self, name):
        return next(player for player in self['players'] if player['name'] == name)

    def by_id(self, id):
        return next(player for player in self['players'] if player['id'] == id)

    def __str__(self):
        return '\n'.join([str(s) for s in self['players']])

    def __len__(self):
        return len(self['players'])
