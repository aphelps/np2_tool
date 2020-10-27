
import math
import requests
from neptune.Player import Player

# Star format:
#     {
#         u'e': 4,             # Economy
#         u'uid': 294,         # Star ID
#         u'i': 3,             # Industry
#         u'puid': 5,          # Player ID
#         u'n': u'Sham',       # Name
#         u's': 2,             # Science
#         u'r': 40,            # Resources
#         u'exp': 0,
#         u'v': u'1',          # Visible
#         u'y': u'5.04934006', # y location
#         u'x': u'0.69888656', # x location
#         u'ga': 0,
#         u'st': 290           # Ships
#     }
class Star(object):
    ECONOMY = 'economy'
    INDUSTRY = 'industry'
    SCIENCE = 'science'

    # 3 hours per LY
    LIGHT_YEAR_TIME = 3

    # 1 star scale = 8 light years observed
    # docs say 1/16, but seem to be wrong
    LIGHT_YEAR_SCALE = 8

    def __init__(self, info, universe):
        self.universe = universe
        self.visible = int(info['v'])
        self.name = info['n']
        self.id = int(info['uid'])
        self.player_id = int(info['puid'])
        self.loc_x = float(info['x'])
        self.loc_y = float(info['y'])

        if self.visible:
            self.ships = int(info['st'])
            self.resources = {
                Star.ECONOMY: int(info['e']),
                Star.INDUSTRY: int(info['i']),
                Star.SCIENCE: int(info['s'])
            }
            self.size = int(info['r'])
            self.gate = int(info['ga'])

            self.costs = self.calculate_costs()
        else:
            self.ships = None

        # Wormhole
        if "wh" in info:
            self.wh = int(info['wh'])
        else:
            self.wh = None

    def calculate_costs(self):
        e = self.resources[Star.ECONOMY] + 1
        i = self.resources[Star.INDUSTRY] + 1
        s = self.resources[Star.SCIENCE] + 1
        return {
            Star.ECONOMY: math.floor(
                (10.0 * e * e) / (self.size / 100.0)),
            Star.INDUSTRY: math.floor(
                (15.0 * i * i) / (self.size / 100.0)),
            Star.SCIENCE: math.floor(
                (20.0 * s * s) / (self.size / 100.0)),
        }

    # TODO: This should probably take tech range levels into account?
    def distance_to(self, target):
        distance = math.sqrt(
            (self.loc_x - target.loc_x) ** 2 +
            (self.loc_y - target.loc_y) ** 2)

        if isinstance(target, Star) and target.wh and target.wh == self.id:
            hours = 24
        else:
            hours = int(math.ceil(distance * Star.LIGHT_YEAR_SCALE * Star.LIGHT_YEAR_TIME))

        return {
            'distance': distance * Star.LIGHT_YEAR_SCALE,
            'time': hours
        }

    def upgrade(self, resource):
        amount = self.costs[resource]
        data = {'type': 'batched_orders',
                'order': 'upgrade_%s,%d,%d' % (resource, self.id, amount),
                'version': '',
                'game_number': '%d' % self.universe.state["game_id"]}
        print("Star.upgrade(): command: %s" % data)

        result = requests.post(
            'https://np.ironhelmet.com/prequest/batched_orders',
            data=data,
            cookies=self.universe.state["cookies"])
        print('Star.upgrade(): status=%d text=%s' % (
            result.status_code, result.text))
        if result.status_code != 200:
            print(f"Star.upgrade(): failed, status={result.status_code}")
            return False
        response = result.json()
        if response["event"] != "order:ok":
            print(f"Star.upgrade(): failed '{response['report']}'")
            return False

        # Apply the upgrade to the model
        self.resources[resource] += 1
        self.costs = self.calculate_costs()

        return True

    def ships_in_range(self, stars, fleets, players, hours):
        counts = {
            Player.SELF: 0,
            Player.FRIEND: 0,
            Player.NEUTRAL: 0,
            Player.FOE: 0
        }
        for star in stars:
            if star.visible:
                distance = self.distance_to(star)
                if distance['time'] <= hours:
                    player = players.by_id(star.player_id)
                    counts[player['state']] += star.ships
        for fleet in fleets:
            distance = self.distance_to(fleet)
            if distance['time'] <= hours:
                player = players.by_id(fleet.player_id)
                counts[player['state']] += fleet.ships

        return counts