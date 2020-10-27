# "50": {
#   "uid": 50,
#   "sp": 0.041666666666666664,
#   "l": 0,
#   "o": [
#     [
#       0,
#       294,
#       1,
#       0
#     ],
#     [
#       0,
#       82,
#       1,
#       0
#     ]
#   ],
#   "n": "Peacock I",
#   "puid": 5,
#   "exp": 140,
#   "y": "4.96296426",
#   "x": "0.71448864",
#   "st": 3372,
#   "lx": "0.72189505",
#   "ly": "4.92196113"
# },
class Fleet(object):
    def __init__(self, info):
        self.name = info['n']
        self.id = int(info['uid'])
        self.player_id = int(info['puid'])
        self.loc_x = float(info['lx'])
        self.loc_y = float(info['ly'])
        self.ships = int(info['st'])

    def __str__(self):
        return f"{self.name:>20}: id:{self.id:<3} ships:{self.ships:<5} player:{self.player_id}"