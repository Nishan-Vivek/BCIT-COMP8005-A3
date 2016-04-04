import socket
import sys
from multiprocessing import Pool
import threading
import os
import time
import csv

DEBUG = True
SERVER_PORT = 5000
SERVER_ADDRESS = 'localhost'
PROC_NUM = 10
THREAD_PER_PROC = 10
REPEAT = 10
SOCKET_TIMEOUT = 0
PAYLOAD = "This is the payload"


def print_d(message, debug=True):
    """Prints message if debug is true."""
    if debug:
        print(message, file=sys.stderr)


def getClientID():
    return "PID:{0}".format(os.getpid()) + "-" + threading.current_thread().getName()


def messaging2(sock, message):
    stats = ClientStats()
    stats.client_id = getClientID()
    stats.req_w = REPEAT
    stats.req_c += 0
    try:
        starttime = time.time()
        for x in range(REPEAT):
            print_d('sending "%s"' % message, DEBUG)
            sock.sendall(message.encode())
            data = sock.recv(1024).decode()
            if data:
                stats.req_c += 1
                stats.data_sent += sys.getsizeof(message)
                print_d('received "%s"' % data, DEBUG)
    except Exception as e:
        print_d(e)
        # endtime = time.time()
        # totalTime = endtime - starttime
        # if stats.req_c != 0:
        #     stats.avg_rtt = totalTime / stats.req_c
        # return stats
    finally:
        endtime = time.time()
        totalTime = endtime - starttime
        if stats.req_c != 0:
            stats.avg_rtt = totalTime / stats.req_c
        return stats


def messaging(sock, message):
    try:
        print_d('sending "%s"' % message, DEBUG)
        sock.sendall(message.encode())
        data = sock.recv(1024).decode()
        print_d('received "%s"' % data, DEBUG);
    except:
        raise


class ClientStats():
    def __init__(self):
        self.client_id = 0
        self.req_c = 0
        self.req_w = 0
        self.data_sent = 0
        self.avg_rtt = 0


class ClientThread(threading.Thread):
    def __init__(self, server_address):
        threading.Thread.__init__(self)
        self.server_address = server_address
        self.statistics = {}

    def run(self):
        try:
            # Create a TCP/IP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if SOCKET_TIMEOUT != 0:
                sock.settimeout(SOCKET_TIMEOUT)

            print_d("PID:{0}".format(
                os.getpid()) + "-" + threading.current_thread().getName() + ' connecting to %s port %s ' % self.server_address)
            sock.connect(self.server_address)
            message = PAYLOAD

            # Send the payload the REPEAT number of times or indefitealy if REPEAT = 0
            self.statistics[getClientID()] = messaging2(sock, message)

        # close sockets on exceptions and completion
        except Exception as e:
            print_d(
                "PID:{0}".format(os.getpid()) + "-" + threading.current_thread().getName() + " encountered " + repr(e))
            sock.close()
        finally:
            sock.close()

        print_d("PID:{0}".format(os.getpid()) + "-" + threading.current_thread().getName() + " ending Thread")

    def join(self, *args, **kwargs):
        super(ClientThread, self).join(*args, **kwargs)
        return self.statistics


def client_process(*args):
    print_d("PID:{0}".format(os.getpid()) + " created.")
    threads = []
    server_address = (sys.argv[1], SERVER_PORT)
    statistics = {}

    for _ in range(THREAD_PER_PROC):
        threads.append(ClientThread(server_address))

    [x.start() for x in threads]

    for x in threads:
        x.join()
        statistics.update(x.statistics)

    print_d("PID:{0}".format(os.getpid()) + " Ending Process")

    return statistics


if __name__ == '__main__':
    statistics = {}
    pool = Pool(processes=PROC_NUM)
    results = pool.map(client_process, range(PROC_NUM))
    pool.close()
    pool.join()
    print_d("All processes ended")
    # print_d(type(results))
    for x in results:
        statistics.update(x)
    print_d("Writing statistics to clientStats.csv")
    with open('clientStats.csv', 'w', newline='') as csvfile:
        filewriter = csv.writer(csvfile, dialect='excel')
        filewriter.writerow(["ClientID", "Completed Connections", "Wanted Connections", "Data Sent", "Average RTT"])
        for x in statistics:
            filewriter.writerow([statistics[x].client_id, statistics[x].req_c, statistics[x].req_w, statistics[x].data_sent, statistics[x].avg_rtt])

