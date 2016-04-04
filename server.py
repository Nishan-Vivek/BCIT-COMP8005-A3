import select
from socket import *
import sys
import queue
import signal
import csv

DEBUG = True
LISTEN_PORT = 10001
BUFFER_SIZE = 1024


def print_d(message, debug=True):
    """Prints message if debug is true."""
    if debug:
        print(message, file=sys.stderr)


def exit_gracefully(signum, frame):
    # restore the original signal handler as otherwise evil things will happen
    # in raw_input when CTRL+C is pressed, and our signal handler is not re-entrant
    signal.signal(signal.SIGINT, original_sigint)

    try:
        if input("\nReally quit? (y/n)> ").lower().startswith('y'):
            write_stats(client_id_counter, client_data_counter)

            sys.exit(1)

    except KeyboardInterrupt:
        print("Ok ok, quitting")
        sys.exit(1)

    # restore the exit gracefully handler here
    signal.signal(signal.SIGINT, exit_gracefully)


def run_program():
    # Main Loop
    while True:
        events = epoll.poll(1)
        for fileno, event in events:

            # handle readable client connections
            if event & select.EPOLLIN:
                # handle new connection requests on listen socket
                if fileno == listen_socket.fileno():
                    client_socket, client_address = listen_socket.accept()
                    print_d("{0} connected.".format(client_address))
                    client_socket.setblocking(0)
                    epoll.register(client_socket.fileno(), select.EPOLLIN | select.EPOLLET)
                    client_addresses[client_socket.fileno()] = client_address
                    client_sockets[client_socket.fileno()] = client_socket
                    message_queues[client_socket.fileno()] = queue.Queue()
                    epoll.modify(listen_socket.fileno(), select.EPOLLIN | select.EPOLLET)
                else:
                    try:
                        data = client_sockets[fileno].recv(BUFFER_SIZE)
                        data_string = data.decode()
                        if data:
                            print_d(
                                "Received: {0} ".format(data_string) + " from {0} ".format(client_addresses[fileno]),
                                DEBUG)
                            client_id = ("{0}".format(client_addresses[fileno]))
                            message_queues[fileno].put(data)
                            epoll.modify(fileno, select.EPOLLOUT | select.EPOLLET)
                            client_id_counter.append(client_id)
                            client_data_counter.append(sys.getsizeof(data_string))
                        else:  # close connection
                            print_d("Closing connection with {0}, no data".format(client_addresses[fileno]))
                            epoll.unregister(fileno)
                            client_sockets[fileno].close()
                            del message_queues[fileno]
                            del client_addresses[fileno]
                            del client_sockets[fileno]
                    except Exception as e:
                        print_d("Closing connection to {0}, ".format(client_addresses[fileno]) + repr(e))
                        epoll.unregister(fileno)
                        client_sockets[fileno].close()
                        del message_queues[fileno]
                        del client_addresses[fileno]
                        del client_sockets[fileno]

            # handle writeable connections
            elif event & select.EPOLLOUT:
                try:
                    next_msg = message_queues[fileno].get_nowait()
                except Exception:
                    print_d("Closing connection to {0}, ".format(client_addresses[fileno]) + repr(e))
                    epoll.unregister(fileno)
                    client_sockets[fileno].close()
                    del message_queues[fileno]
                    del client_addresses[fileno]
                    del client_sockets[fileno]
                else:
                    try:
                        print_d("Sending " + next_msg.decode() + " to {0}".format(client_addresses[fileno]), DEBUG)
                        client_sockets[fileno].sendall(next_msg)
                        epoll.modify(fileno, select.EPOLLIN | select.EPOLLET)
                    except Exception:
                        print_d("Closing connection to {0}, ".format(client_addresses[fileno]) + repr(e))
                        epoll.unregister(fileno)
                        client_sockets[fileno].close()
                        del message_queues[fileno]
                        del client_addresses[fileno]
                        del client_sockets[fileno]

            # handle closed or erroneous connections
            else:
                pass
                # print_d("Closing connection to {0}".format(client_addresses[fileno]))
                # epoll.unregister(fileno)
                # client_sockets[fileno].close()
                # del message_queues[fileno]
                # del client_addresses[fileno]
                # del client_sockets[fileno]  # # Sockets ready to write to


class ClientStats():
    def __init__(self):
        self.client_id = 0
        self.data_sent = 0
        self.req_c = 0


def write_stats(client_id_counter, client_data_counter):
    server_statistics = {}

    for i, client_id in enumerate(client_id_counter):
        if client_id not in server_statistics:
            server_statistics[client_id] = ClientStats()
            server_statistics[client_id].client_id = client_id
            server_statistics[client_id].req_c += 1
            server_statistics[client_id].data_sent += client_data_counter[i]
        else:
            server_statistics[client_id].req_c += 1
            server_statistics[client_id].data_sent += client_data_counter[i]

    print_d("Writing stats to server_e_Stats.csv")
    with open('server_e_Stats.csv', 'w', newline='') as csvfile:
        filewriter = csv.writer(csvfile, dialect='excel')
        filewriter.writerow(["ClientID", "Completed Connections", "Data Received"])
        for x in server_statistics:
            filewriter.writerow(
                [server_statistics[x].client_id, server_statistics[x].req_c, server_statistics[x].data_sent])


# Setup Listening Socket
server_address = ('', LISTEN_PORT)
listen_socket = socket(AF_INET, SOCK_STREAM)
listen_socket.setblocking(0)
listen_socket.bind(server_address)
listen_socket.listen(5)

# Dictionaries to track clients and messages.
message_queues = {}
client_addresses = {}
client_sockets = {}
client_id_counter = []
client_data_counter = []

# create epoll object and register listing socket
epoll = select.epoll()
epoll.register(listen_socket.fileno(), select.EPOLLIN | select.EPOLLET)

if __name__ == '__main__':
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, exit_gracefully)
    run_program()
