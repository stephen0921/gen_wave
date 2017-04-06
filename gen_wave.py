from vcd import VCDWriter
import argparse
import random
import re
import sys
import subprocess


def debug(args):
    """
    function for subparser debug
    """
    m_gen_wave = c_gen_wave(mem_width=args.mem_width)
    if args.mem_data_file is not None:
        m_gen_wave.gen_mem_data(out_file_name=args.mem_data_file,
                                mem_width=args.mem_width,
                                mem_depth=args.mem_depth)


def gen(args):
    """
    function for subparser gen
    """
    m_gen_wave = c_gen_wave(mem_width=args.mem_width,
                            bus_width=args.bus_width)
    m_gen_wave.get_signal(in_fh=args.input_signal_file)
    m_gen_wave.write_fsdb(in_fh=args.input_mem_file,
                          out_fh=args.output_fsdb)


class my_exception(Exception):
    def __str__(self):
        print "Some thing is wrong!"


class c_signal(object):
    def __init__(self, pos, name, width):
        self.pos = pos
        self.name = name
        self.width = width
        self.padding = False

    def set_padding(self):
        self.padding = True


class c_gen_wave(object):
    """
    gen_wave is a class for turning memory data into vcd or fsdb wave

    """
    def __init__(self, mem_width=64, bus_width=32, order='l2h'):
        super(c_gen_wave, self).__init__()
        self.mem_width = mem_width
        self.bus_width = bus_width
        self.order = order

    def greeting(self, message):
        print '\033[32m %s \033[0m' % message

    def info(self, message):
        print '\033[36m %s \033[0m' % message

    def error(self, message):
        print '\033[31m %s \033[0m' % message

    def write_fsdb(self, in_fh, out_fh):
        try:
            match = re.search('(.*)\.fsdb', out_fh.name)
            if match is None:
                vcd_file_name = out_fh.name + '.vcd'
                fsdb_file_name = out_fh.name + '.fsdb'
                out_fh.close()
                subprocess.Popen(['rm', '-rf', out_fh.name])
            else:
                vcd_file_name = match.group(1) + '.vcd'
                fsdb_file_name = out_fh.name
                out_fh.close()
            vcd_fh = open(vcd_file_name, 'w')
            writer = VCDWriter(vcd_fh, timescale='1 ns', date='today')
            line_num = 0
            signal_vcd = dict()
            # create a dummy clock signal
            clk_vcd = writer.register_var(
                    scope='u_dut', name='clk',
                    var_type='reg', size=1)
            for line in in_fh:
                num = self.mem_width / self.bus_width
                clk_value = 1
                for cnt in range(0, num):
                    timestamp = line_num*self.mem_width / self.bus_width + cnt
                    # print "timestamp = %d" % timestamp
                    bin_list = []
                    bus_data_in_hex = line[(cnt*self.bus_width/4):
                                           ((cnt + 1)*self.bus_width/4)]
                    for hex_4bits in bus_data_in_hex:
                        bin_4bits = bin(int(hex_4bits, 16))
                        bin_4bits = '%04d' % int((bin_4bits)[2:])
                        bin_list.append(bin_4bits)
                    bus_data = ''.join(bin_list)
                    # print "bus_data = %s" % bus_data
                    # register_var for each signal
                    for signal_obj in self.signal_lists:
                        if signal_vcd.get(signal_obj.name) is None:
                            signal_vcd[signal_obj.name] = writer.register_var(
                                scope='u_dut', name=signal_obj.name,
                                var_type='reg', size=signal_obj.width)
                    for signal_obj in self.signal_lists:
                        # print "name = %s" % signal_obj.name
                        # print "pos = %d" % signal_obj.pos
                        # print "width = %d" % signal_obj.width
                        if self.order == 'l2h':
                            value = bus_data[
                                self.bus_width - signal_obj.pos
                                - signal_obj.width:
                                self.bus_width - signal_obj.pos]
                        else:
                            value = bus_data[
                                self.bus_width - signal_obj.pos - 1:
                                self.bus_width - signal_obj.pos - 1
                                + signal_obj.width]
                        # print "%s = %s" % (signal_obj.name, value)
                        if signal_obj.padding:
                            writer.change(signal_vcd[signal_obj.name],
                                          2*timestamp, 0)
                        else:
                            writer.change(signal_vcd[signal_obj.name],
                                          2*timestamp, value)
                    writer.change(clk_vcd, 2*timestamp, clk_value)
                    clk_value = 0
                    writer.change(clk_vcd, 2*timestamp+1, clk_value)
                    clk_value = 1
                line_num = line_num + 1
            in_fh.close()
            vcd_fh.close()

            child1 = subprocess.Popen(['vcd2fsdb', vcd_file_name,
                                       '-o', fsdb_file_name],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
            info_list = child1.stdout.read()
            if re.search(
                    'VCD file is converted to FSDB file successfully',
                    info_list,) is not None:
                self.greeting(
                    'FSDB file (%s) is created successfully!' % fsdb_file_name)
            else:
                self.error(
                    'Creating FSDB file (%s) is failed!' % fsdb_file_name)
                raise my_exception

            child2 = subprocess.Popen(['rm', '-rf',
                                       'novas.conf',
                                       'novas.rc', 'nWaveLog', 'vcd2fsdbLog'],
                                      stdout=subprocess.PIPE)

            child2.stdout.read()
        except Exception as X:
            print(X)

    def get_signal(self, in_fh):
        try:
            if self.order == 'l2h':
                start_pos = 0
            else:
                start_pos = self.bus_width - 1
            width = 0
            sum = 0
            self.signal_lists = []
            for line in in_fh:
                if re.search('\s*^#', line) or \
                   re.search('^\s*\n$', line) or \
                   re.search('^\s$', line):
                    continue
                else:
                    if self.order == 'l2h':
                        start_pos = start_pos + width
                    else:
                        start_pos = start_pos - width
                    # print "start_pos = %d" % start_pos
                    match = re.search("(\w+):\s*(\d+)", line)
                    if match:
                        signal_name = match.group(1)
                        signal_width = int(match.group(2))
                    else:
                        match = re.search("\w+", line)
                        if match:
                            signal_name = match.group(0)
                            signal_width = 1
                        else:
                            print line
                            print "Unknow format in signal file"
                            raise my_exception
                    m_signal = c_signal(pos=start_pos,
                                        name=signal_name, width=signal_width)
                    self.signal_lists.append(m_signal)
                    width = signal_width
                    sum = sum + width
            in_fh.close()
            if sum < self.bus_width:  # padding
                self.info(
                    'dont_care signal will be put into the waveform \
since signal width sum %d is less \
than bus_width %d' % (sum, self.bus_width))

                if self.order == 'l2h':
                    start_pos = start_pos + width
                else:
                    start_pos = start_pos - width

                m_padding_signal = c_signal(pos=start_pos,
                                            name='dont_care',
                                            width=(self.bus_width-sum))
                m_padding_signal.set_padding()
                self.signal_lists.append(m_padding_signal)
            if sum > self.bus_width:  # if not start_pos == width - 1:
                self.error('All signal width sum %d should \
not exceed %d' % (sum, self.bus_width))
                # print "start_pos = %d" % start_pos
                # print "width = %d" % width
                raise my_exception
        except Exception:
            exit()

    def gen_mem_data(self, out_file_name, mem_width=64, mem_depth=16):
        random_times = mem_width / 8
        if random_times == 0:
            raise ValueError("mem_width can not be less than 8")
        if not (mem_width % 8 == 0):
            raise ValueError("mem_width must can be divide by 8")
        self.mem_data_list = []
        for i in range(0, mem_depth):
            mem_data = None
            # print "== %d ==" % i
            for j in range(0, random_times):
                rand_8bits = '%02x' % random.randint(0, 255)
                if mem_data:
                    mem_data = mem_data + str(rand_8bits)
                else:
                    mem_data = str(rand_8bits)
                # print "mem_data = %s" % mem_data

            self.mem_data_list.append(mem_data)
            self.mem_data_list.append('\n')
        out = open(out_file_name, 'w')
        out.writelines(self.mem_data_list)
        out.close()
        self.greeting(
            'mem_data_file (%s) is created successfully!' % out_file_name)
        # print self.mem_data_list


def main():
    # get options from command line
    parser = argparse.ArgumentParser(
        description='Process memory data and gen waveform.')

    subparsers = parser.add_subparsers()

    gen_parser = subparsers.add_parser('gen')

    gen_parser.add_argument('-mw', dest='mem_width',
                            default=64, type=int,
                            help='the memory data width, default is 64')
    gen_parser.add_argument('-bw', dest='bus_width',
                            type=int, default=32,
                            help='the monitor bus width, default is 32')
    gen_parser.add_argument('-im',
                            dest='input_mem_file',
                            metavar='in-file',
                            type=argparse.FileType('r'),
                            required=True,
                            help='the memory data input file')
    gen_parser.add_argument('-is',
                            dest='input_signal_file',
                            metavar='in-file',
                            type=argparse.FileType('r'),
                            required=True,
                            help='the signal input file')
    gen_parser.add_argument('-o',
                            dest='output_fsdb',
                            metavar='out-file',
                            type=argparse.FileType('w'),
                            default='gen.fsdb',
                            help='the fsdb ouput file, default is gen.fsdb')
    gen_parser.set_defaults(func=gen)

    debug_parser = subparsers.add_parser('debug')

    debug_parser.add_argument('-mw', dest='mem_width',
                              default=64, type=int,
                              help='the memory data width, default is 64')
    debug_parser.add_argument('-gm', dest='mem_data_file',
                              default=None, action='store',
                              help='generate memory data file')
    debug_parser.add_argument('-md', dest='mem_depth',
                              type=int, default=16,
                              help='the memory depth, default is 16')

    debug_parser.set_defaults(func=debug)

    if len(sys.argv) == 1:
        args = parser.parse_args(['-h'])
    else:
        args = parser.parse_args()

    args.func(args)


if __name__ == '__main__':
    main()
