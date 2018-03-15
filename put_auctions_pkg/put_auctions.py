# TODO: It is completed only for 'insider' auctions

# Examples of usage:
# ./put_auctions.py insider planning --wait_for_result
# ./put_auctions.py insider run
# or
# ./put_auctions.py insider planning --wait_for_result && ./put_auctions.py insider run
# ./put_auctions.py insider load-testing --auctions_number 10000 --concurency 1000

import os.path
import json
import argparse
import contextlib
import tempfile
from dateutil.tz import tzlocal
from gevent.pool import Pool
from gevent.subprocess import Popen
from gevent.subprocess import check_output
from datetime import datetime, timedelta
from random import randint
import iso8601
from configparser import RawConfigParser
import io


PWD = os.path.dirname(os.path.realpath(__file__))
CWD = os.getcwd()

TENDER_DATA = \
    {'simple': {'path': os.path.join(PWD, '..', 'data', 'simple.json'),
                'worker': 'auction_worker',
                'id': 'NOT DEFINED YET',
                'config': 'auction_worker_defaults.yaml',
                'tender_id_base': '1'},
    'insider': {'path': os.path.join(PWD, '..', 'data', 'insider.json'),
                 'worker': 'auction_insider',
                 'id': '1'*32,
                 'config': 'auction_worker_insider.yaml',
                 'tender_id_base': '1'}}


@contextlib.contextmanager
def update_auctionPeriod(path, auction_type, start_time=None,
                         time_offset_sec=120):
    if not start_time:
        start_time = datetime.now(tzlocal())
    else:
        start_time = iso8601.parse_date(start_time)

    time_offset_sec = randint(0, time_offset_sec)
    time_offset = timedelta(seconds=time_offset_sec)
    with open(path) as file:
        data = json.loads(file.read())
    new_start_time = (start_time + time_offset).isoformat()

    if auction_type == 'simple':
        data['data']['auctionPeriod']['startDate'] = new_start_time
    elif auction_type == 'multilot':
        for lot in data['data']['lots']:
            lot['auctionPeriod']['startDate'] = new_start_time

    with tempfile.NamedTemporaryFile(delete=False) as auction_file:
        json.dump(data, auction_file)
        auction_file.seek(0)
    yield auction_file.name
    auction_file.close()


# TODO: should be studied and improved
def planning(worker_directory_path, tender_file_path, worker, auction_id,
             config, start_time, time_offset, wait_for_result=False):
    with update_auctionPeriod(tender_file_path, auction_type='simple',
                              start_time=start_time,
                              time_offset_sec=time_offset) \
            as auction_file:
        command = '{0}/bin/{1} planning {2} {0}/etc/{3} ' \
                  '--planning_procerude partial_db --auction_info {4}'\
            .format(worker_directory_path, worker, auction_id, config,
                    auction_file)
        check_output(command.split())
        # p = Popen('{0}/bin/{1} planning {2} {0}/etc/{3} --planning_procerude '
        #           'partial_db --auction_info {4}'
        #           .format(CWD, worker, auction_id, config,
        #                   auction_file).split())
        # if wait_for_result:
        #     p.wait()


def run(worker_directory_path, tender_file_path, worker, auction_id, config,
        start_time, time_offset, wait_for_result=False):
    with update_auctionPeriod(tender_file_path, auction_type='simple',
                              start_time=start_time,
                              time_offset_sec=time_offset) \
            as auction_file:
        p = Popen('{0}/bin/{1} run {2} {0}/etc/{3} --planning_procerude '
                  'partial_db --auction_info {4}'
                  .format(worker_directory_path, worker, auction_id, config,
                          auction_file).split())
        if wait_for_result:
            p.wait()


def load_testing(worker_directory_path, tender_file_path, worker, config,
                 count, initial_number, tender_id_base, concurency,
                 run_auction=False, start_time=None, time_offset=120,
                 wait_for_result=False):
    positions = 4

    auction_id_template = \
        tender_id_base * (32 - positions) + '{{0:0{}d}}'.format(positions)

    pool = Pool(concurency)
    for i in xrange(initial_number, count):
        auction_id = auction_id_template.format(i)
        pool.apply_async(
            planning,
            (worker_directory_path, tender_file_path, worker, auction_id,
             config, start_time, i*3600, wait_for_result)
        )
        pool.wait_available()
    pool.join()


def main(auction_type, action_type, worker_directory_path=CWD,
         tender_file_path='', run_auction=False, wait_for_result=False,
         data=''):

    with open(data, 'r') as f:
        sample_config = f.read()
    config = RawConfigParser(allow_no_value=True)
    config.read_file(io.BytesIO(sample_config))

    PARAMS = {}
    for option in config.options(auction_type):
        PARAMS[option] = config.get(auction_type, option)

    auctions_number = int(PARAMS['auctions_number'])
    initial_number = int(PARAMS['initial_number'])
    concurency = int(PARAMS['concurency'])
    start_time = PARAMS['start_time']
    time_offset = int(PARAMS['time_offset'])

    actions = globals()

    tender_id_base_local = TENDER_DATA[auction_type]['tender_id_base'] if \
        not PARAMS['tender_id_base'] else PARAMS['tender_id_base']

    tender_file_path = tender_file_path or TENDER_DATA[auction_type]['path']
    if action_type in [elem.replace('_', '-') for elem in actions]:
        if action_type == 'load-testing':
            load_testing(worker_directory_path,
                         tender_file_path,
                         TENDER_DATA[auction_type]['worker'],
                         TENDER_DATA[auction_type]['config'],
                         auctions_number,
                         initial_number,
                         tender_id_base_local,
                         concurency,
                         run_auction,
                         start_time,
                         time_offset,
                         wait_for_result)
        else:
            actions.get(action_type)(worker_directory_path,
                                     tender_file_path,
                                     TENDER_DATA[auction_type]['worker'],
                                     TENDER_DATA[auction_type]['id'],
                                     TENDER_DATA[auction_type]['config'],
                                     start_time,
                                     time_offset,
                                     wait_for_result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('auction_type', type=str)
    parser.add_argument('action_type', type=str)
    parser.add_argument('--worker_directory_path', type=str, nargs='?',
                        default=CWD)
    parser.add_argument('--tender_file_path', type=str, nargs='?', default='')
    parser.add_argument('--run_auction', action='store_true')
    parser.add_argument('--wait_for_result', action='store_true')
    parser.add_argument('--data', type=str, nargs='?', default='')

    args = parser.parse_args()

    main(args.auction_type, args.action_type, args.worker_directory_path,
         args.tender_file_path, args.run_auction, args.wait_for_result,
         args.data)
