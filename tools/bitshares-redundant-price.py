# DEX validated last price

# finds several low latency nodes
# if all have same last price, 
    # return (price)
    # elif mode(price) 
    # else median(price)

# handles non-responsive nodes
# approximately 60 seconds delayed w/ 5 nodes of redundancy

' BTS: litepresence1 '

# http://docs.pybitshares.com
from bitshares import BitShares
from bitshares.market import Market
import ast
from statistics import mean,median,mode
import time


BitCURRENCY = 'USD'
BitASSET = 'BTS'
BitPAIR = BitASSET + ":" + BitCURRENCY
SATOSHI = 0.00000001
ANTISAT = 1 / SATOSHI


def nodes(timeout=20, pings=999999, crop=99, noprint=False,
          include=False, exclude=False, suffix=True, master=False):

    # timeout : seconds to ping until abort per node
    # pings   : number of good nodes to find until satisfied (0 none, 999 all)
    # suffix  : checks each node for no suffix plus with /ws or /wss
    # noprint : disables printing, only returns list of good nodes
    # master  : check only nodes listed in bitshares/ui/master
    # crop    : return only best nodes
    from multiprocessing import Process, Value, Array
    from bitshares.blockchain import Blockchain
    from bitshares import BitShares
    from datetime import datetime
    import requests
    import time
    import sys
    import os


    # include and exclude custom nodes
    included, excluded = [], []
    if include:
        included = []

    if exclude:
        excluded = []

    # web scraping methods
    def clean(raw):
        return ((str(raw).replace('"', " "))
                .replace("'", " ")).replace(',', ' ')

    def parse(cleaned):
        return [t for t in cleaned.split() if t.startswith('wss')]

    def validate(parsed):
        v = [i for i in parsed if (('test' not in i) and ('fake' not in i))]
        for i in range(len(v)):
            if v[i].endswith('/'):
                v[i] = v[i][:-1]
        for i in range(len(v)):
            if v[i].endswith('/ws'):
                v[i] = v[i][:-3]
        for i in range(len(v)):
            if v[i].endswith('/wss'):
                v[i] = v[i][:-4]
        # these are known to require /ws extension
        ws = ['wss://relinked.com',
              'wss://bitshares.crypto.fans',
              'wss://this.uptick.rocks']
        if suffix:
            wss = [(i + '/wss') for i in v]
            ws = [(i + '/ws') for i in v]
            v = v + wss + ws
        else:
            for i in range(len(v)):
                if v[i] in ws:
                    v[i] += '/ws'
                else:
                    v[i] += '/wss'
        return v

    # ping the blockchain and return latency
    def ping(n, num, arr):
        try:
            start = time.time()
            chain = Blockchain(
                bitshares_instance=BitShares(n, num_retries=0), mode='head')
            ping_latency = time.time() - start
            current_block = chain.get_current_block_num()
            blocktimestamp = abs(
                chain.block_timestamp(current_block) + utc_offset)
            block_latency = time.time() - blocktimestamp
            if block_latency < (ping_latency + 4):
                num.value = ping_latency
            else:
                num.value = 111111
        except:
            num.value = 222222
            pass

    # Disable / Enable printing
    def blockPrint():
        if noprint:
            sys.stdout = open(os.devnull, 'w')

    def enablePrint():
        if noprint:
            sys.stdout = sys.__stdout__

    # gather list of nodes from github
    blockPrint()
    begin = time.time()
    utc_offset = (datetime.fromtimestamp(begin) -
                  datetime.utcfromtimestamp(begin)).total_seconds()
    print ('=====================================')
    print(('found %s nodes stored in script' % len(included)))
    urls = []
    # scrape from github
    git = 'https://raw.githubusercontent.com'
    url = git + '/bitshares/bitshares-ui/master/app/api/apiConfig.js'
    urls.append(url)
    if not master:
        url = git + '/bitshares/bitshares-ui/staging/app/api/apiConfig.js'
        urls.append(url)
        url = git + '/CryptoBridge/cryptobridge-ui/'
        url += 'e5214ad63a41bd6de1333fd98d717b37e1a52f77/app/api/apiConfig.js'
        urls.append(url)
        url = git + '/litepresence/extinction-event/master/bitshares-nodes.py'
        urls.append(url)

    # searched selected sites for Bitshares nodes
    validated = [] + included
    for u in urls:
        attempts = 3
        while attempts > 0:
            try:
                raw = requests.get(u).text
                v = validate(parse(clean(raw)))
                print(('found %s nodes at %s' % (len(v), u[:65])))
                validated += v
                attempts = 0
            except:
                print(('failed to connect to %s' % u))
                attempts -= 1
                pass

    # remove known bad nodes from test
    if len(excluded):
        excluded = sorted(excluded)
        print(('remove %s known bad nodes' % len(excluded)))
        validated = [i for i in validated if i not in excluded]

    validated = sorted(list(set(validate(parse(clean(validated))))))

    # attempt to contact each websocket
    print ('=====================================')
    print(('found %s total nodes - no duplicates' % len(validated)))
    print ('=====================================')
    print (validated)
    pinging = min(pings, len(validated))
    if pinging:
        print ('=====================================')
        enablePrint()
        print(('%s searching for %s nodes; timeout %s sec; est %.1f minutes' % (
            time.ctime(), pinging, timeout, timeout * len(validated) / 60.0)))
        blockPrint()
        print ('=====================================')
        pinged, timed, down, stale, expired = [], [], [], [], []
        for n in validated:
            if len(pinged) < pinging:
                # use multiprocessing module to enforce timeout
                num = Value('d', 999999)
                arr = Array('i', list(range(0)))
                p = Process(target=ping, args=(n, num, arr))
                p.start()
                p.join(timeout)
                if p.is_alive() or (num.value > timeout):
                    p.terminate()
                    p.join()
                    if num.value == 111111:  # head block is stale
                        stale.append(n)
                    if num.value == 222222:  # connect failed
                        down.append(n)
                    if num.value == 999999:  # timeout reached
                        expired.append(n)
                else:
                    pinged.append(n)        # connect success
                    timed.append(num.value)  # connect success time
                print(('ping:', ('%.2f' % num.value), n))

        # sort websockets by latency
        pinged = [x for _, x in sorted(zip(timed, pinged))]
        timed = sorted(timed)
        unknown = sorted(
            list(set(validated).difference(pinged + down + stale + expired)))

        # report outcome
        print('')
        print((len(pinged), 'of', len(validated),
               'nodes are active with latency less than', timeout))
        print(('fastest node', pinged[0], 'with latency', ('%.2f' % timed[0])))
        if len(excluded):
            print('')
            print ('EXCLUDED nodes:')
            print('')
            for i in range(len(excluded)):
                print(('XXXX', excluded[i]))
        if len(unknown):
            print('')
            print ('UNTESTED nodes:')
            print('')
            for i in range(len(unknown)):
                print(('????', unknown[i]))
        if len(down):
            print('')
            print ('DOWN nodes:')
            print('')
            for i in range(len(down)):
                print(('DOWN', down[i]))
        if len(stale):
            print('')
            print ('STALE nodes:')
            print('')
            for i in range(len(stale)):
                print(('SSSS', stale[i]))
        if len(expired):
            print('')
            print ('TIMEOUT nodes:')
            print('')
            for i in range(len(expired)):
                print(('TTTT', expired[i]))
        if len(pinged):
            print ('')
            print ('GOOD nodes:')
            print ('')
            for i in range(len(pinged)):
                print((('%.2f' % timed[i]), pinged[i]))

        ret = pinged[-crop:]
    else:
        ret = validated[-crop:]

    print ('')
    print (ret)
    print ('')
    enablePrint()
    print(('elapsed', ('%.2f' % (time.time() - begin))))
    return ret


def dex(  # Public AND Private API Bitshares
        command, amount=ANTISAT, price=None,
        depth=1, expiration=ANTISAT):


    if command == 'last':

        # the most recent transation in this MARKET
        print(('Bitshares API', command))
        raw = MARKET.ticker()['latest']
        price = float(raw)
        # print (price)
        return price

def market(n):
    global MARKET
    MARKET = Market(BitPAIR, bitshares_instance=BitShares(n, num_retries=0))
    

redundancy = 5

node_list = nodes(timeout=3, pings=redundancy, crop=99, noprint=True,
          include=False, exclude=False, suffix=False, master=False)

node_list.append('wss://some.shitty.node/wss')

print(node_list)

start = time.time()
redundant_last = []
for i in range(len(node_list)):
    ret = 'No data from node: '
    try:
        market(node_list[i])
        ret = dex('last')
        redundant_last.append(ret)
    except:
        pass
    print (ret, node_list[i])


print (redundant_last)


if len(set(redundant_last)) ==1:
    last = redundant_last[0]
    print ('common last')
else:
    try:
        last = mode(redundant_last)
        print ('mode last')
    except:
        last = median(redundant_last)
        print ('median last')


print(last)
print ('elapsed: ', (time.time()-start))
