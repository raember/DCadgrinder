from os import listdir

class UUIDs:
    KAMI   = 'f0290083-87e6-43c9-ad07-3e4ea501a98f'
    POODIE = 'e53da975-39ff-4d04-ac62-0bd99d6e2579'


class Names:
    KAMI = 'Kami_the_Miner'
    POODIE = 'Poodie'

class HARs:
    GAMEAPIS_PLAYER_NAME = ["gameapis/player_name/{}".format(f) for f in listdir('gameapis/player_name')][0]
    GAMEAPIS_PLAYER_UUID = ["gameapis/player_uuid/{}".format(f) for f in listdir('gameapis/player_uuid')][0]