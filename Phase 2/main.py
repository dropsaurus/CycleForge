import os
import argparse

MemSize = 1000
def twos_complement(n, width=32):
    return bin(n & (2 ** width - 1))[2:].zfill(width)

def nint(s, base, bits=32):
    num = int(s, base)
    if num >= 2 ** (bits - 1):
        num -= 2 ** bits
    return num

class InsMem(object):
    def __init__(self, name, iDir):
        self.id = name

        with open(os.path.join(iDir, 'imem.txt')) as im:
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
    def __init__(self, name, iDir, oDir):
        self.id = name
        self.iDir = iDir
        self.oDir = oDir
        with open(os.path.join(iDir, 'dmem.txt')) as dm:
            self.DMem = [data.replace("\n", "") for data in dm.readlines()]
        self.DMem.extend('0' * (MemSize - len(self.DMem)))

    def readInstr(self, ReadAddress):
        # read data memory
        # return 32 bit hex val
        # Changing 8bit to 32 bit to get the value
        if 0 <= ReadAddress < (len(self.DMem)):
            address_start = ReadAddress - (ReadAddress % 4)
            bin_instruction = self.DMem[address_start] + self.DMem[address_start + 1] + self.DMem[address_start + 2] + self.DMem[address_start + 3]
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
        resPath = os.path.join(self.oDir, self.id + "_DMEMResult.txt")
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
        self.IF = {"nop": True, "PC": 0}
        self.ID = {"nop": True, "Instr": 0}
        self.EX = {"nop": True, "Read_data1": 0, "Read_data2": 0, "Imm": 0, "Rs": 0, "Rt": 0, "Wrt_reg_addr": 0,
                   "is_I_type": False, "rd_mem": 0,
                   "wrt_mem": 0, "alu_op": 0, "wrt_enable": 0}
        self.MEM = {"nop": True, "ALUresult": 0, "Store_data": 0, "Rs": 0, "Rt": 0, "Wrt_reg_addr": 0, "rd_mem": 0,
                    "wrt_mem": 0, "wrt_enable": 0}
        self.WB = {"nop": True, "Wrt_data": 0, "Rs": 0, "Rt": 0, "Wrt_reg_addr": 0, "wrt_enable": 0}
        self.SS_IF = {"nop": False, "PC": 0}


class registerPipeline(object):
    def __init__(self):
        self.IF_ID = {"PC": 0, "rawInstruction": 0}
        self.ID_EX = {"PC": 0, "instruction": 0, "rs": 0, "rt": 0}
        self.EX_MEM = {"PC": 0, "instruction": 0, "ALUresult": 0, "rt": 0}
        self.MEM_WB = {"PC": 0, "instruction": 0, "Wrt_data": 0, "ALUresult": 0, "rt": 0}


class checkHazards():
    def hazardRegWrite(self, pr: registerPipeline, rs):
        return rs != 0 and pr.MEM_WB["instruction"] and pr.MEM_WB["instruction"]["registerWrite"] and \
            pr.MEM_WB["instruction"]["Wrt_reg_addr"] == rs

    def hazardLoad(self, pr: registerPipeline, rs1, rs2):
        return pr.ID_EX["instruction"] and pr.ID_EX["instruction"]["rd_mem"] and \
            (pr.ID_EX["instruction"]["Wrt_reg_addr"] == int(rs1, 2) or pr.ID_EX["instruction"]["Wrt_reg_addr"] == int(
                rs2, 2))

    def hazardMEM(self, pr: registerPipeline, rs):
        return pr.MEM_WB["instruction"] and pr.MEM_WB["instruction"]["registerWrite"] and \
            pr.MEM_WB["instruction"]["Wrt_reg_addr"] != 0 and \
            pr.MEM_WB["instruction"]["Wrt_reg_addr"] == rs

    def hazardEX(self, pr: registerPipeline, rs):
        return pr.EX_MEM["instruction"] and pr.EX_MEM["instruction"]["registerWrite"] and not pr.EX_MEM["instruction"][
            "rd_mem"] and \
            pr.EX_MEM["instruction"]["Wrt_reg_addr"] != 0 and \
            pr.EX_MEM["instruction"]["Wrt_reg_addr"] == rs

class Core(object):
    def __init__(self, iDir, oDir, imem, dmem):
        self.myRF = RegisterFile(oDir)
        self.cycle = 0
        self.halted = False
        self.iDir = iDir
        self.oDir = oDir
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
        self.state.IF["nop"] = False
        self.regPipeline = registerPipeline()
        self.checkHazards = checkHazards()


class SingleStageCore(Core):
    def __init__(self, iDir, oDir, imem, dmem):
        super(SingleStageCore, self).__init__(iDir, os.path.join(oDir, 'SS_'), imem, dmem)
        self.opFilePath = os.path.join(oDir, 'StateResult_SS.txt')

    def fetch(self):
        self.binary_instruction_type = self.ext_imem.readInstr(self.state.SS_IF["PC"])
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
            self.nextState.SS_IF["nop"] = True

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
            self.ALUResult = twos_complement(self.nextState.SS_IF["PC"] + 4)
            self.offset = nint(self.offset, 2, len(self.offset))

    def memory(self):
        if self.wrt_mem == 1 and self.nextState.SS_IF["nop"] == False:
            self.ALUResult = dmem_ss.readInstr(self.register_Address)

        elif self.wrt_mem == 2 and self.nextState.SS_IF["nop"] == False:
            self.ext_dmem.writeDataMem(self.register_Address, self.store_data)

        if self.nextState.SS_IF["nop"] == False:
            if self.is_bj_type:
                self.nextState.SS_IF["PC"] += int(self.offset)
            else:
                self.nextState.SS_IF["PC"] += 4
        if self.state.SS_IF["nop"] == False:
            self.IC += 1

    def write_Back(self):
        if self.write_back == 0 and self.nextState.SS_IF["nop"] == False:
            index= int(self.rd_mem, 2)
            if index!=0 :
                self.myRF.writeRF(index, self.ALUResult)

    def step(self):
        self.fetch()
        self.decode()
        if self.state.SS_IF["nop"]:
            self.write_back = 1
            self.wrt_mem = 0
            self.alu_op = 20
            self.is_bj_type = False

        self.execute()
        self.memory()
        self.write_Back()

        if self.state.SS_IF["nop"]:
            self.halted = True

        self.myRF.outputRF(self.cycle)  # dump RF
        self.printState(self.nextState, self.cycle)  # print states after executing cycle 0, cycle 1, cycle 2 ...

        self.state.SS_IF["nop"] = self.nextState.SS_IF["nop"]  # The end of the cycle and updates the current state with the values calculated in this cycle
        self.state.SS_IF["PC"] = self.nextState.SS_IF["PC"]
        self.cycle += 1
        self.alu_op = 0
        self.write_back = 0
        self.wrt_mem = 0
        self.is_bj_type = False
        return self.IC

    def printState(self, state, cycle):
        printstate = ["-" * 70 + "\n", "State after executing cycle: " + str(cycle) + "\n"]
        printstate.append("IF.PC: " + str(state.SS_IF["PC"]) + "\n")
        printstate.append("IF.nop: " + str(state.SS_IF["nop"]) + "\n")

        if (cycle == 0):
            perm = "w"
        else:
            perm = "a"
        with open(self.opFilePath, perm) as wf:
            wf.writelines(printstate)

    def performance_metric(self):
        IC = self.IC
        CPI = float(self.cycle / IC)
        IPC = float(1 / CPI)

        result_format = f"Performance of Single Stage:\n" \
                        f"#Cycles -> {self.cycle}\n" \
                        f"#Instructions -> {IC}\n" \
                        f"CPI -> {CPI}\n" \
                        f"IPC -> {IPC}\n"

        with open(self.oDir[:-3] + "PerformanceMetrics.txt", 'w') as file:
            file.writelines(result_format)

class FiveStageCore(Core):
    def __init__(self, iDir, oDir, imem, dmem):
        super(FiveStageCore, self).__init__(iDir, os.path.join(oDir, 'FS_'), imem, dmem)
        self.opFilePath = os.path.join(oDir, 'StateResult_FS.txt')

    def write_Back(self):
        if not self.state.WB["nop"]:
            instruction = self.regPipeline.MEM_WB["instruction"]

            if instruction["registerWrite"]:
                Reg_addr = instruction["Wrt_reg_addr"]
                Wrt_reg_data = self.regPipeline.MEM_WB["Wrt_data"]
                if Reg_addr != 0:
                    self.myRF.writeRF(Reg_addr,twos_complement(Wrt_reg_data))

    def memory(self):
        self.nextState.WB["nop"] = self.state.MEM["nop"]

        if not self.state.MEM["nop"]:
            pc = self.regPipeline.EX_MEM["PC"]
            instruction = self.regPipeline.EX_MEM["instruction"]
            alu_result = self.regPipeline.EX_MEM["ALUresult"]
            rs2 = self.regPipeline.EX_MEM["Rs2"]

            if instruction["wrt_mem"]:
                writeData = nint(self.myRF.readRF(rs2),2)
                writeAddress = alu_result
                writeData=twos_complement(writeData,32)
                self.ext_dmem.writeDataMem(writeAddress, writeData)

            if instruction["rd_mem"]:
                readAddress = alu_result
                wrt_mem_data = nint(self.ext_dmem.readInstr(readAddress),2,32)

            if instruction["memReg"] == 1:
                self.regPipeline.MEM_WB["Wrt_data"] = wrt_mem_data

            else:
                self.regPipeline.MEM_WB["Wrt_data"] = alu_result

            self.regPipeline.MEM_WB["PC"] = pc
            self.regPipeline.MEM_WB["instruction"] = instruction

    def execute(self):
        self.nextState.MEM["nop"] = self.state.EX["nop"]

        if not self.state.EX["nop"]:
            pc = self.regPipeline.ID_EX["PC"]
            instruction = self.regPipeline.ID_EX["instruction"]
            rs2 = self.regPipeline.ID_EX["Rs2"]
            self.state.EX = self.regPipeline.ID_EX["instruction"]

            if self.state.EX["imm"] != "X":
                op2 = self.state.EX["imm"]

            else:
                op2 = self.state.EX["Read_data2"]

                # addition
            if self.state.EX["aluControl"] == "0010":
                alu_result = self.state.EX["Read_data1"] + op2

            # subtraction
            if self.state.EX["aluControl"] == "0110":
                alu_result = self.state.EX["Read_data1"] - op2

            # and operation
            if self.state.EX["aluControl"] == "0000":
                alu_result = self.state.EX["Read_data1"] & op2

            # or operation
            if self.state.EX["aluControl"] == "0001":
                alu_result = self.state.EX["Read_data1"] | op2

            # xor operation
            if self.state.EX["aluControl"] == "0011":
                alu_result = self.state.EX["Read_data1"] ^ op2

            self.regPipeline.EX_MEM["PC"] = pc
            self.regPipeline.EX_MEM["instruction"] = instruction
            self.regPipeline.EX_MEM["ALUresult"] = alu_result
            self.regPipeline.EX_MEM["Rs2"] = rs2

    def decode(self):
        self.nextState.EX["nop"] = self.state.ID["nop"]

        if not self.state.ID["nop"]:
            instructionReverse = self.regPipeline.IF_ID["rawInstruction"][::-1]
            self.regPipeline.ID_EX["PC"] = self.regPipeline.IF_ID["PC"]
            pc = self.regPipeline.IF_ID["PC"]
            opcode = instructionReverse[0:7]

            # R-type instruction
            if opcode == "1100110":
                rs1 = instructionReverse[15:20][::-1]
                rs2 = instructionReverse[20:25][::-1]
                rd = instructionReverse[7:12][::-1]
                func7 = instructionReverse[25:32][::-1]
                func3 = instructionReverse[12:15][::-1] + func7[1]

                aluContol = {"0000": "0010", "0001": "0110", "1110": "0000", "1100": "0001", "1000": "0011"}
                self.regPipeline.ID_EX["instruction"] = {"nop": False, "Read_data1": nint(self.myRF.readRF(int(rs1, 2)),2),
                                                         "Read_data2": nint(self.myRF.readRF(int(rs2, 2)),2),
                                                         "imm": "X", "pcJump": 0, "Rs": int(rs1, 2), "Rt": int(rs2, 2),
                                                         "Wrt_reg_addr": int(rd, 2), "is_I_type": False, "rd_mem": 0,
                                                         "aluSource": 0, "aluControl": aluContol[func3],
                                                         "wrt_mem": 0, "alu_op": "10", "registerWrite": 1, "branch": 0,
                                                         "memReg": 0}

            # I-type instruction
            if opcode == "1100100":
                rs1 = instructionReverse[15:20][::-1]
                imm = instructionReverse[20:32][::-1]
                rd = instructionReverse[7:12][::-1]
                func3 = instructionReverse[12:15][::-1]

                aluContol = {"000": "0010", "111": "0000", "110": "0001", "100": "0011"}
                self.regPipeline.ID_EX["instruction"] = {"nop": False, "Read_data1": nint(self.myRF.readRF(int(rs1, 2)),2),
                                                         "Read_data2": 0,
                                                         "imm": nint(imm,2, 12), "pcJump": 0, "Rs": int(rs1, 2),
                                                         "Rt": 0,
                                                         "Wrt_reg_addr": int(rd, 2), "is_I_type": True, "rd_mem": 0,
                                                         "aluSource": 1, "aluControl": aluContol[func3],
                                                         "wrt_mem": 0, "alu_op": "00", "registerWrite": 1, "branch": 0,
                                                         "memReg": 0}

            # I-type instruction
            if opcode == "1100000":
                rs1 = instructionReverse[15:20][::-1]
                imm = instructionReverse[20:32][::-1]
                rd = instructionReverse[7:12][::-1]
                func3 = instructionReverse[12:15][::-1]

                self.regPipeline.ID_EX["instruction"] = {"nop": False, "Read_data1": nint(self.myRF.readRF(int(rs1, 2)),2),
                                                         "Read_data2": 0,
                                                         "imm": nint(imm,2, 12), "pcJump": 0, "Rs": int(rs1, 2),
                                                         "Rt": 0,
                                                         "Wrt_reg_addr": int(rd, 2), "is_I_type": False, "rd_mem": 1,
                                                         "aluSource": 1, "aluControl": "0010",
                                                         "wrt_mem": 0, "alu_op": "00", "registerWrite": 1, "branch": 0,
                                                         "memReg": 1}

            # S-type instruction
            if opcode == "1100010":
                rs1 = instructionReverse[15:20][::-1]
                rs2 = instructionReverse[20:25][::-1]
                imm = instructionReverse[7:12] + instructionReverse[25:32]
                imm = imm[::-1]

                self.regPipeline.ID_EX["instruction"] = {"nop": False, "Read_data1": nint(self.myRF.readRF(int(rs1, 2)),2),
                                                         "Read_data2": nint(self.myRF.readRF(int(rs2, 2)),2),
                                                         "imm": int(imm, 2), "Rs": int(rs1, 2), "Rt": int(rs2, 2),
                                                         "pcJump": 0,
                                                         "is_I_type": False, "rd_mem": 0, "aluSource": 1,
                                                         "aluControl": "0010", "alu_op": "00",
                                                         "Wrt_reg_addr": "X", "wrt_mem": 1, "registerWrite": 0,
                                                         "branch": 0, "memReg": "X"}

            # SB-type instruction
            if opcode == "1100011":
                rs1 = instructionReverse[15:20][::-1]
                rs2 = instructionReverse[20:25][::-1]
                imm = "0" + instructionReverse[8:12] + instructionReverse[25:31] + instructionReverse[7] + \
                      instructionReverse[31]
                imm = imm[::-1]
                func3 = instructionReverse[12:15][::-1]

                self.regPipeline.ID_EX["instruction"] = {"nop": False, "Read_data1": nint(self.myRF.readRF(int(rs1, 2)),2),
                                                         "Read_data2": nint(self.myRF.readRF(int(rs2, 2)),2),
                                                         "imm": "X", "Rs": int(rs1, 2), "Rt": int(rs2, 2),
                                                         "pcJump": nint(imm, 2,13),
                                                         "is_I_type": False, "rd_mem": 0, "aluSource": 0,
                                                         "aluControl": "0110", "alu_op": "01",
                                                         "Wrt_reg_addr": "X", "wrt_mem": 0, "registerWrite": 0,
                                                         "branch": 1, "memReg": "X", "func3": func3}

            # UJ-type instruction
            if opcode == "1111011":
                rs1 = instructionReverse[15:20][::-1]
                imm = "0" + instructionReverse[21:31] + instructionReverse[20] + instructionReverse[12:20] + \
                      instructionReverse[31]
                imm = imm[::-1]
                rd = instructionReverse[7:12][::-1]

                self.regPipeline.ID_EX["instruction"] = {"nop": False, "Read_data1": pc, "Read_data2": 4,
                                                         "imm": "X", "Rs": 0, "Rt": 0,
                                                         "pcJump": nint(imm,2, 21),
                                                         "is_I_type": False, "rd_mem": 0, "aluSource": 1,
                                                         "aluControl": "0010", "alu_op": "10",
                                                         "Wrt_reg_addr": int(rd, 2), "wrt_mem": 0, "registerWrite": 1,
                                                         "branch": 1, "memReg": 0, "func3": "X"}

            if self.checkHazards.hazardRegWrite(
                    self.regPipeline, self.regPipeline.ID_EX["instruction"]["Rs"]
            ):
                self.regPipeline.ID_EX["instruction"]["Read_data1"] = self.regPipeline.MEM_WB["Wrt_data"]

            if self.checkHazards.hazardRegWrite(
                    self.regPipeline, self.regPipeline.ID_EX["instruction"]["Rt"]
            ):
                self.regPipeline.ID_EX["instruction"]["Read_data2"] = self.regPipeline.MEM_WB["Wrt_data"]

            self.regPipeline.ID_EX["Rs1"] = self.regPipeline.ID_EX["instruction"]["Rs"]
            self.regPipeline.ID_EX["Rs2"] = self.regPipeline.ID_EX["instruction"]["Rt"]

            if self.checkHazards.hazardEX(
                    self.regPipeline, self.regPipeline.ID_EX["Rs1"]
            ):
                self.regPipeline.ID_EX["instruction"]["Read_data1"] = self.regPipeline.EX_MEM["ALUresult"]

            elif self.checkHazards.hazardMEM(
                    self.regPipeline, self.regPipeline.ID_EX["Rs1"]
            ):
                self.regPipeline.ID_EX["instruction"]["Read_data1"] = self.regPipeline.MEM_WB["Wrt_data"]

            if self.regPipeline.ID_EX["instruction"]["imm"] == "X":
                if self.checkHazards.hazardEX(self.regPipeline, self.regPipeline.ID_EX["Rs2"]):
                    self.regPipeline.ID_EX["instruction"]["Read_data2"] = self.regPipeline.EX_MEM["ALUresult"]

                elif self.checkHazards.hazardMEM(self.regPipeline, self.regPipeline.ID_EX["Rs2"]):
                    self.regPipeline.ID_EX["instruction"]["Read_data2"] = self.regPipeline.MEM_WB["Wrt_data"]

            if self.regPipeline.ID_EX["instruction"]["branch"]:
                if self.regPipeline.ID_EX["instruction"]["func3"] == "000" and self.regPipeline.ID_EX["instruction"][
                    "Read_data1"] - self.regPipeline.ID_EX["instruction"]["Read_data2"] == 0:
                    self.nextState.IF["nop"] = False
                    self.nextState.IF["PC"] = pc + (self.regPipeline.ID_EX["instruction"]["pcJump"])
                    self.state.IF["nop"] = self.nextState.EX["nop"] = self.nextState.ID["nop"] = True

                elif self.regPipeline.ID_EX["instruction"]["func3"] == "001" and self.regPipeline.ID_EX["instruction"][
                    "Read_data1"] - self.regPipeline.ID_EX["instruction"]["Read_data2"] != 0:
                    self.nextState.IF["nop"] = False
                    self.nextState.IF["PC"] = pc + (self.regPipeline.ID_EX["instruction"]["pcJump"])
                    self.state.IF["nop"] = self.nextState.EX["nop"] = self.nextState.ID["nop"] = True

                elif self.regPipeline.ID_EX["instruction"]["func3"] == "X":
                    self.nextState.IF["nop"] = False
                    self.nextState.IF["PC"] = pc + (self.regPipeline.ID_EX["instruction"]["pcJump"])
                    self.state.IF["nop"] = self.nextState.ID["nop"] = True

                else:
                    self.nextState.EX["nop"] = True

        else:
            self.regPipeline.ID_EX = {"PC": 0, "instruction": 0, "rs": 0, "rt": 0}

    def fetch(self):
        self.nextState.ID["nop"] = self.state.IF["nop"]

        if not self.state.IF["nop"]:
            self.regPipeline.IF_ID["rawInstruction"] = self.ext_imem.readInstr(self.state.IF["PC"])
            self.regPipeline.IF_ID["PC"] = self.state.IF["PC"]
            instructionReverse = self.regPipeline.IF_ID["rawInstruction"][::-1]

            opcode = instructionReverse[0:7]
            if opcode == "1111111":
                self.nextState.ID["nop"] = self.state.IF["nop"] = True

            else:
                self.nextState.IF["nop"] = False
                self.nextState.IF["PC"] = self.state.IF["PC"] + 4

                if self.checkHazards.hazardLoad(self.regPipeline, instructionReverse[15:20][::-1],
                                                instructionReverse[20:25][::-1]):
                    self.nextState.ID["nop"] = True
                    self.nextState.IF["PC"] = self.state.IF["PC"]

    def step(self):
        self.write_Back()
        self.memory()
        self.execute()
        self.decode()
        self.fetch()

        if self.state.IF["nop"] and self.state.ID["nop"] and self.state.EX["nop"] and self.state.MEM["nop"] and self.state.WB["nop"]:
            self.halted = True

        self.myRF.outputRF(self.cycle)
        self.state = self.nextState
        self.nextState = State()
        self.cycle += 1
    def performance_metric(self, IC):
        CPI = float(self.cycle / IC)
        IPC = float(1 / CPI)

        result_format = f"\nPerformance of Five Stage:\n" \
                        f"#Cycles -> {self.cycle}\n" \
                        f"#Instructions -> {IC}\n" \
                        f"CPI -> {CPI}\n" \
                        f"IPC -> {IPC}\n"

        with open(self.oDir[:-3] + "PerformanceMetrics.txt", 'a') as file:
            file.writelines(result_format)

if __name__ == "__main__":

    # parse arguments for input file location
    parser = argparse.ArgumentParser(description='RV32I processor')
    parser.add_argument('--iodir', default="", type=str, help='Directory containing code.')
    args = parser.parse_args()

    current_directory = os.getcwd()
    print("Current Working Directory:", current_directory)

    ioDir = os.path.abspath(args.iodir)
    # Output directory creation
    try:
        os.makedirs(os.path.join(ioDir, 'output_NN2685'))
    except FileExistsError:
        print("Output Folder Exists")

    iDir = os.path.join(os.path.abspath(args.iodir), 'input')

    oDir = os.path.join(os.path.abspath(args.iodir), 'output_NN2685')

    all_items = os.listdir(iDir)
    for item in all_items:
        if os.path.isdir(os.path.join(iDir, item)):
            try:
                os.makedirs(os.path.join(oDir, item))
            except FileExistsError:
                print(f"TestCase folder already exists")

            itDir = os.path.join(iDir, item)
            otDir = os.path.join(oDir, item)
            imem = InsMem("Imem", itDir)
            dmem_ss = DataMem("SS", itDir, otDir)
            dmem_fs = DataMem("FS", itDir, otDir)

            ssCore = SingleStageCore(itDir, otDir, imem, dmem_ss)
            fsCore = FiveStageCore(itDir, otDir, imem, dmem_fs)
            IC=0

            while (True):
                if not ssCore.halted:
                    IC = ssCore.step()

                if not fsCore.halted:
                    fsCore.step()

                if ssCore.halted and fsCore.halted:
                    break

            ssCore.performance_metric()
            fsCore.performance_metric(IC)
            # dump SS and FS data mem.
            dmem_ss.outputDataMem()
            dmem_fs.outputDataMem()
