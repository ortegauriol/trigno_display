'''
start from command line
read config file with targets defined

loop over trials:
    execute a trial
    save file

'''
import sys
import numpy as np
from ConfigParser import SafeConfigParser
from argparse import ArgumentParser
from PyDragonfly import Dragonfly_Module, MT_EXIT, CMessage, copy_to_msg, copy_from_msg
import Dragonfly_config as rc
from dragonfly_utils import respond_to_ping
from PySide import QtGui, QtCore
import pyqtgraph as pg

class Config(object):
    pass

class FastDisplay(QtGui.QWidget):
    def __init__(self, config_file, server):
        #self.parent = parent
        #self.counter = 0
        super(FastDisplay, self).__init__()
        self.load_config(config_file)
        self.init_gui()
        self.listening = True
        self.setup_dragonfly(server)

    def load_config(self, config_file):
        cfg = SafeConfigParser()
        cfg.read(config_file)
        self.config = Config()
        self.config.nsamp = cfg.getint('main', 'sfreq') # sampling frequency
        self.config.nchan = cfg.getint('main', 'nchan')
        #self.channel_range= cfg.getint('main', 'nchan')
        self.config.bytes = cfg.getint('main', 'byteschan')
        self.config.perchan = 27 #at each iteration there are at least 27 samples per each of the 16 EMG channels per packet
        self.config.npt   = self.config.nchan * self.config.perchan
        
        sys.stdout.write("nsamp: " + str(self.config.nsamp) + "\n")
        sys.stdout.write("nchan: " + str(self.config.nchan) + "\n")
        sys.stdout.write("perchan: " + str(self.config.perchan) + "\n")
        sys.stdout.write("npt: " + str(self.config.npt) + "\n")
        
    def setup_dragonfly(self, server):
        subscriptions = [MT_EXIT, \
                         rc.MT_PING, \
                         rc.MT_DAQ_DATA, \
                         rc.MT_SAMPLE_GENERATED, \
                         rc.MT_TRIGNO_DATA]
        self.mod = Dragonfly_Module(0, 0)
        self.mod.ConnectToMMM(server)
        for sub in subscriptions:
            self.mod.Subscribe(sub)
        self.mod.SendModuleReady()
        print "Connected to Dragonfly at ", server

    def init_gui(self):
        # create a window with 14 plots (7 rows x 2 columns)
        ## create a window with 8 plots (4 rows x 2 columns)

        win = pg.GraphicsWindow(title="Trigno display")
        win.resize(1000,600)
        win.setWindowTitle('Trigno display')
        pg.setConfigOptions(antialias=True)

        #cols, rows = 2, 4
        cols = 2
        rows = self.config.nchan / cols
        self.npt = 1000
        self.axes = np.empty((rows, cols), dtype=object)
        for i in xrange(rows):
            for j in xrange(cols):
                ax = win.addPlot(title="EMG%d" % (i * cols + j))
                #ax.disableAutoRange(axis=None)
                self.axes[i,j] = ax.plot(np.random.normal(1,1, size=1000))
            win.nextRow()
            
        self.old_data = np.zeros((self.config.nchan, self.npt))
        self.new_data = np.zeros((self.config.nchan, self.npt))
        
        timer = QtCore.QTimer(self)
        timer.connect(timer, QtCore.SIGNAL("timeout()"), self.timer_event)
        timer.start(0)

    def process_message(self, msg):
        # read a Dragonfly message
        msg_type = msg.GetHeader().msg_type
        dest_mod_id = msg.GetHeader().dest_mod_id
        if  msg_type == MT_EXIT:
            if (dest_mod_id == 0) or (dest_mod_id == self.mod.GetModuleID()):
                print 'Received MT_EXIT, disconnecting...'
                self.mod.SendSignal(rc.MT_EXIT_ACK)
                self.mod.DisconnectFromMMM()
                return
        elif msg_type == rc.MT_PING:
            respond_to_ping(self.mod, msg, 'FastDisplay')
        else:
            # if it is a NiDAQ message from channels 0-7, plot the data
            #self.counter += 1
            if msg_type == rc.MT_TRIGNO_DATA:
                sys.stdout.write("*")
                #sys.stdout.flush()
                mdf = rc.MDF_TRIGNO_DATA()
                copy_from_msg(mdf, msg)
                # add data to data buffers (necessary, or just use graphics buffers?)
                # update plots to new data buffers
                buf = mdf.T
            elif msg_type == rc.MT_SAMPLE_GENERATED:
                sys.stdout.write("#")
                sys.stdout.flush()
                buf = np.random.normal(1, 1, size=(432,))
            else:
                return False
            # Slide 27 points
            self.new_data[:,:-self.config.perchan] = self.old_data[:,self.config.perchan:]
            print (***)
            for i in xrange(self.config.nchan):
                #if i == 0:
                #    print mdf.buffer[perchan * i:perchan * (i + 1)].size
                self.new_data[i, -self.config.perchan:] = buf[i:self.config.nchan * self.config.perchan:self.config.nchan]
                self.axes.flat[i].setData(self.new_data[i])
                #sys.stdout.write("*")
                #sys.stdout.flush()
            self.old_data[:] = self.new_data[:]
            #self.parent.processEvents()        

    def timer_event(self):
        done = False
        #sys.stdout.write("~")
        sys.stdout.flush()
        while not done:
            msg = CMessage()
            rcv = self.mod.ReadMessage(msg, 0)
            if rcv == 1:
                    self.process_message(msg)

                #elif msg_type == MT_EXIT:
                #    self.exit()
                #    done = True

            else:
                done = True

                    
if __name__ == "__main__":
    parser = ArgumentParser(description = 'Real-time display of 8-channel EMG')
    parser.add_argument(type=str, dest='config')
    parser.add_argument(type=str, dest='mm_ip', nargs='?', default='127.0.0.1:7111')
    args = parser.parse_args()
    print("Using config file=%s, MM IP=%s" % (args.config, args.mm_ip))
    app = QtGui.QApplication(sys.argv)
    fd = FastDisplay(args.config, args.mm_ip)
    exit_status = app.exec_()
    sys.exit(exit_status)
    print "Got here"
