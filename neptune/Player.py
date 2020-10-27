class Player(dict):
    SELF = 0
    FRIEND = 1
    NEUTRAL = 2
    FOE = 3

    def __init__(self, player_info):
        dict.__init__(self,
                      name=player_info['alias'],
                      id=int(player_info['uid']),
                      state=Player.NEUTRAL)

    def relationship(self):
        if self['state'] == Player.SELF:
            return 'self'
        if self['state'] == Player.FRIEND:
            return 'friend'
        if self['state'] == Player.NEUTRAL:
            return 'neutral'
        if self['state'] == Player.FOE:
            return 'foe'

    def __str__(self):
        return f"{self['name']:>20}: id:{self['id']:<3} state:{self.relationship()}"
