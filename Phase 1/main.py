import os
import argparse

MemSize = 1000  # memory size, in reality, the memory size should be 2^32, but for this lab, for the space resaon, we keep it as this large number, but the memory is still 32-bit addressable.


def twos_complement(n, width=32):
    return bin(n & (2 ** width - 1))[2:].zfill(width)


def nint(s, base, bits=32):
    num = int(s, base)
    if num >= 2 ** (bits - 1):
        num -= 2 ** bits
    return num


class InsMem(object):
    def __init__(self, name, ioDir):
        self.id = name

        with open(ioDir + "/imem.txt") as im:
            self.IMem = [data.replace("\n", "") for data in im.readlines()]


    def readInstr(self, ReadAddress):
        # read instruction memory
        # return 32 bit hex val
        if 0 <= ReadAddress < (len(self.IMem)):
            address_start = ReadAddress - (ReadAddress % 4)
            bin_instruction = self.IMem[address_start] + self.IMem[address_start + 1] + self.IMem[address_start + 2] + \
                              self.IMem[address_start + 3]
            # hex_instruction = hex(int(bin_instruction, 2))[2:].zfill(8)
            return bin_instruction
        else:
            return "00000000"


class DataMem(object):
    def __init__(self, name, ioDir):
        self.id = name
        self.ioDir = ioDir
        with open(ioDir + "/dmem.txt") as dm:
            self.DMem = [data.replace("\n", "") for data in dm.readlines()]
        self.DMem.extend('0' * (MemSize - len(self.DMem)))

    def readInstr(self, ReadAddress):
        # read data memory
        # return 32 bit hex val
        # Changing 8bit to 32 bit to get the value
        if 0 <= ReadAddress < (len(self.DMem)):
            address_start = ReadAddress - (ReadAddress % 4)
            bin_instruction = self.DMem[address_start] + self.DMem[address_start + 1] + self.DMem[address_start + 2] + \
                              self.DMem[address_start + 3]
            # hex_instruction = hex(int(bin_instruction, 2))[2:].zfill(8)
            return bin_instruction
        else:
            return "00000000"

    def writeDataMem(self, Address, WriteData):
        address_start = Address - (Address % 4)
        self.DMem[address_start] = WriteData[0:8]
        self.DMem[address_start + 1] = WriteData[8:16]
        self.DMem[address_start + 2] = WriteData[16:24]
        self.DMem[address_start + 3] = WriteData[24:32]

    def outputDataMem(self):
        resPath = self.ioDir + "\\" + self.id + "_DMEMResult.txt"
        with open(resPath, "w") as rp:
            rp.writelines([str(data).zfill(8) + "\n" for data in self.DMem])


class RegisterFile(object):
    def __init__(self, ioDir):
        self.outputFile = ioDir + "RFResult.txt"
        self.Registers = ['0' for i in range(32)]

    def readRF(self, Reg_addr):
        if 0 <= Reg_addr <= 31:
            return self.Registers[Reg_addr]

    def writeRF(self, Reg_addr, Wrt_reg_data):
        if 0 <= Reg_addr <= 31:
            self.Registers[Reg_addr] = Wrt_reg_data

    def outputRF(self, cycle):
        op = ["-" * 70 + "\n", "State of RF after executing cycle:" + str(cycle) + "\n"]
        op.extend([str(val).zfill(32) + "\n" for val in self.Registers])
        if (cycle == 0):
            perm = "w"
        else:
            perm = "a"
        with open(self.outputFile, perm) as file:
            file.writelines(op)


class State(object):
    def __init__(self):
        self.IF = {"nop": False, "PC": 0}


class Core(object):
    def __init__(self, ioDir, imem, dmem):
        self.myRF = RegisterFile(ioDir)
        self.cycle = 0
        self.halted = False
        self.ioDir = ioDir
        self.state = State()
        self.nextState = State()
        self.ext_imem = imem
        self.ext_dmem = dmem
        self.PC = 0;
        self.rs1 = 0
        self.rs2 = 0
        self.read_rs1 = 0
        self.read_rs2 = 0
        self.rd = 0
        self.imm = 0
        self.binary_instruction = 0
        self.offset = 0
        self.alu_op = 0
        self.write_back = 0
        self.wrt_mem = 0
        self.ALUResult = 0
        self.register_Address = 0
        self.store_data = 0
        self.IC=0
        self.is_bj_type = False

    def fetch(self):
        self.binary_instruction_type = self.ext_imem.readInstr(self.state.IF["PC"])

    # Decodes the instruction and decides the operation to be performed in the execute stage; reads the operands from the register file.
    def decode(self):
        bin_instruction = self.binary_instruction_type.zfill(32)

        opcode = bin_instruction[25:32]
        func3 = bin_instruction[17:20]
        func7 = bin_instruction[0:7]

        # R-Type
        if opcode == '0110011':
            self.rs2 = bin_instruction[7:12].zfill(5)  # rs2
            self.rs1 = bin_instruction[12:17].zfill(5)
            self.rd_mem = bin_instruction[20:25].zfill(5)
            self.write_back = 0
            self.read_rs1 = self.myRF.readRF(int(self.rs1, 2))
            self.read_rs2 = self.myRF.readRF(int(self.rs2, 2))
            if func7 == '0000000':
                # ADD
                if func3 == '000':
                    self.alu_op = 0
                # XOR
                elif func3 == '100':
                    self.alu_op = 1
                # OR
                elif func3 == '110':
                    self.alu_op = 2
                # AND
                elif func3 == '111':
                    self.alu_op = 3

            elif func7 == '0100000':
                # SUB
                if func3 == '000':
                    self.alu_op = 4

        # I Type
        elif opcode == '0010011':
            self.rs1 = bin_instruction[12:17].zfill(5)  # rs1
            self.rd_mem = bin_instruction[20:25].zfill(5)  # rd
            self.imm = bin_instruction[0:12].zfill(12)
            self.read_rs1 = self.myRF.readRF(int(self.rs1, 2))
            self.read_rs2 = self.imm
            self.write_back = 0
            # ADDI
            if func3 == '000':
                self.alu_op = 5
            # XORI
            elif func3 == '100':
                self.alu_op = 6
            # ORI
            elif func3 == '110':
                self.alu_op = 7
            # ANDI
            elif func3 == '111':
                self.alu_op = 8


        # I Type LW
        elif opcode == '0000011':
            self.alu_op = 9
            self.rs1 = bin_instruction[12:17].zfill(5)
            self.rd_mem = bin_instruction[20:25].zfill(5)
            self.imm = bin_instruction[0:12].zfill(12)
            self.read_rs1 = self.myRF.readRF(int(self.rs1, 2))
            self.read_rs2 = self.imm
            self.write_back = 0

        # S Type
        elif opcode == '0100011':
            self.alu_op = 10
            self.rs2 = bin_instruction[7:12]  # rs2
            self.rs1 = bin_instruction[12:17]  # rs1
            self.imm = bin_instruction[0:7] + bin_instruction[20:25]
            self.read_rs1 = self.myRF.readRF(int(self.rs1, 2))
            self.read_rs2 = self.imm
            self.rd_mem = self.myRF.readRF(int(self.rs2, 2))
            self.write_back = 1
            # write_back_signal = False


        # SB-Type
        elif opcode == '1100011':
            self.rs2 = bin_instruction[7:12]
            self.rs1 = bin_instruction[12:17]
            self.read_rs1 = self.myRF.readRF(int(self.rs2, 2))
            self.read_rs2 = self.myRF.readRF(int(self.rs1, 2))
            self.imm = bin_instruction[0] + bin_instruction[24] + bin_instruction[1:7] + bin_instruction[
                                                                                         20:24] + '0'
            self.offset = self.imm
            self.is_bj_type = True
            self.write_back = 1
            # BEQ
            if func3 == '000':
                self.alu_op = 11
            # BNE
            elif func3 == '001':
                self.alu_op = 12


        # JAL
        elif opcode == '1101111':
            self.alu_op = 13
            self.rd_mem = bin_instruction[20:25]
            self.imm = bin_instruction[0] + bin_instruction[12:20] + bin_instruction[11] + bin_instruction[
                                                                                           1:11] + '0'
            self.write_back = 0
            self.is_bj_type = True
            self.offset = self.imm

        elif opcode == '1111111':
            self.nextState.IF["nop"] = True

    # Executes the ALU operation based on ALUop
    def execute(self):
        if self.alu_op == 0 or self.alu_op == 5:
            self.ALUResult = twos_complement(
                nint(self.read_rs1, 2, len(self.read_rs1)) + nint(
                    self.read_rs2, 2, len(self.read_rs2)))

        elif self.alu_op == 1 or self.alu_op == 6:
            self.ALUResult = twos_complement(
                nint(self.read_rs1, 2, len(self.read_rs1)) ^ nint(
                    self.read_rs2, 2, len(self.read_rs2)))

        elif self.alu_op == 3 or self.alu_op == 8:
            self.ALUResult = twos_complement(
                nint(self.read_rs1, 2, len(self.read_rs1)) & nint(
                    self.read_rs2, 2, len(self.read_rs2)))

        elif self.alu_op == 2 or self.alu_op == 7:
            self.ALUResult = twos_complement(
                nint(self.read_rs1, 2, len(self.read_rs1)) | nint(
                    self.read_rs2, 2, len(self.read_rs2)))

        elif self.alu_op == 4:
            self.ALUResult = twos_complement(
                nint(self.read_rs1, 2, len(self.read_rs1)) - nint(
                    self.read_rs2, 2, len(self.read_rs2)))

        elif self.alu_op == 9:
            self.register_Address = int(
                nint(self.read_rs1, 2) + nint(self.read_rs2, 2,
                                              len(self.read_rs2)))
            self.wrt_mem = 1

        elif self.alu_op == 10:
            self.register_Address = int(
                nint(self.read_rs1, 2) + nint(self.read_rs2, 2,
                                              len(self.read_rs2)))
            self.store_data = self.rd_mem
            self.wrt_mem = 2

        elif self.alu_op == 11:
            if nint(self.read_rs1, 2) == nint(self.read_rs2, 2):
                self.offset = nint(self.offset, 2, len(self.offset))
            else:
                self.is_bj_type = False

        elif self.alu_op == 12:
            if nint(self.read_rs1, 2) != nint(self.read_rs2, 2):
                self.offset = nint(self.offset, 2, len(self.offset))
            else:
                self.is_bj_type = False

        elif self.alu_op == 13:
            self.ALUResult = twos_complement(self.nextState.IF["PC"] + 4)
            self.offset = nint(self.offset, 2, len(self.offset))

    def memory(self):
        if self.wrt_mem == 1 and self.nextState.IF["nop"] == False:
            self.ALUResult = dmem_ss.readInstr(self.register_Address)

        elif self.wrt_mem == 2 and self.nextState.IF["nop"] == False:
            self.ext_dmem.writeDataMem(self.register_Address, self.store_data)

        if self.nextState.IF["nop"] == False:
            if self.is_bj_type:
                self.nextState.IF["PC"] += int(self.offset)
            else:
                self.nextState.IF["PC"] += 4
        if self.state.IF["nop"] == False:
            self.IC += 1

    def write_Back(self):
        if self.write_back == 0 and self.nextState.IF["nop"] == False:
            self.myRF.writeRF(int(self.rd_mem, 2), self.ALUResult)

    def performance_metric(self):
        IC = self.IC
        CPI = float(self.cycle / IC)
        IPC = float(1 / CPI)

        result_format = f"Single Stage Core Performance Metrics:\n" \
                        f"Number of Cycles taken -> {self.cycle}\n" \
                        f"Total number of Instructions -> {IC}\n" \
                        f"Cycles per instruction -> {CPI}\n" \
                        f"Instructions per cycle -> {IPC}\n"

        with open(self.ioDir[:-3] + "PerformanceMetrics.txt", 'w') as file:
            file.writelines(result_format)


class SingleStageCore(Core):
    def __init__(self, ioDir, imem, dmem):
        super(SingleStageCore, self).__init__(ioDir + "\\SS_", imem, dmem)
        self.opFilePath = ioDir + "\\StateResult_SS.txt"

    def step(self):
        self.fetch()
        self.decode()
        if self.state.IF["nop"]:
            self.write_back = 1
            self.wrt_mem = 0
            self.alu_op = 20
            self.is_bj_type = False

        self.execute()
        self.memory()
        self.write_Back()

        if self.state.IF["nop"]:
            self.halted = True

        self.myRF.outputRF(self.cycle)  # dump RF
        self.printState(self.nextState, self.cycle)  # print states after executing cycle 0, cycle 1, cycle 2 ...

        self.state.IF["nop"] = self.nextState.IF["nop"]  # The end of the cycle and updates the current state with the values calculated in this cycle
        self.state.IF["PC"] = self.nextState.IF["PC"]
        self.cycle += 1
        self.alu_op = 0
        self.write_back = 0
        self.wrt_mem = 0
        self.is_bj_type = False

    def printState(self, state, cycle):
        printstate = ["-" * 70 + "\n", "State after executing cycle: " + str(cycle) + "\n"]
        printstate.append("IF.PC: " + str(state.IF["PC"]) + "\n")
        printstate.append("IF.nop: " + str(state.IF["nop"]) + "\n")

        if (cycle == 0):
            perm = "w"
        else:
            perm = "a"
        with open(self.opFilePath, perm) as wf:
            wf.writelines(printstate)


if __name__ == "__main__":

    #parse arguments for input file location
    parser = argparse.ArgumentParser(description='RV32I processor')
    parser.add_argument('--iodir', default="", type=str, help='Directory containing the input files.')
    args = parser.parse_args()

    ioDir = os.path.abspath(args.iodir)
    print("IO Directory:", ioDir)

    imem = InsMem("Imem", ioDir)
    dmem_ss = DataMem("SS", ioDir)
    dmem_fs = DataMem("FS", ioDir)
    
    ssCore = SingleStageCore(ioDir, imem, dmem_ss)


    while(True):
        if not ssCore.halted:
            ssCore.step()
        
        if ssCore.halted:
            break
    
    # dump SS and FS data mem.
    dmem_ss.outputDataMem()
    ssCore.performance_metric()