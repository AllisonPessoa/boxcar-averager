"""
FEDERAL UNIVERSITY OF PERNAMBUCO - PHYSICS DEPARTMENT - NANO OPTICS LABORATORY
                            DIGITAL MULTICHANNEL

Graphical interface for communicatig with Arduino Time-Correlated Single Photon Counter device.

                            Allison Pessoa
                                2020

"""
import sys
from PyQt5 import QtCore, QtGui, QtWidgets, uic

from guiqwt.plot import CurveWidget
from guiqwt.builder import make

import pickle
import numpy as np
import time
import os.path

import serial
from serial.tools import list_ports

layout_form = uic.loadUiType("layout.ui")[0]

class Plot():
    def __init__(self, widget_plot, toolbar):
        """ Initializes the plot Widget and adds a item"""
        self.widget_plot = widget_plot
        self.toolbar = toolbar
        self.data =  range(100) #Initial data, arbitrary
        #Curve widget
        self.plotWidget = CurveWidget(self.widget_plot, xlabel=('Tempo'),
                                                ylabel=('Contagens'), xunit=('us'),
                                                yunit=('#'))
        self.plotWidget.add_toolbar(self.toolbar, "default")
        self.plotWidget.register_all_curve_tools()
        #Curve item
        self.item = make.curve(np.asarray(range(len(self.data))),np.asarray(self.data))
        #Curve plot
        self.plot = self.plotWidget.get_plot()
        self.plot.add_item(self.item)
        self.plotWidget.resize(self.widget_plot.size())
        self.plotWidget.show()

    def setData(self, data):
        """ Change the data of the item and replot """
        self.item.set_data(np.asarray(data[0]),np.asarray(data[1]))
        self.plot.do_autoscale()
        self.plot.replot()

    def clearData(self):
        """ Clear the current plot """
        self.setData([[0,1],[0,1]])

    def getData(self):
        """ Get the raw data being displayed at the moment """
        return self.item.get_data() #x,y np arrays

class Worker(QtCore.QObject):
    """ Thread doing the backend """
    measurementStart = False
    measurementAbort = QtCore.pyqtSignal()
    parent = None

    atualizeListPorts = QtCore.pyqtSignal(list)
    emparelhado = False
    ser = None
    mode = 'COUNTER'
    nMode = 0

    atualizeData = QtCore.pyqtSignal(int, list, str)
    b_max = 100 #Número de pontos mostrando no gráfico
    b_pos = 0 #buffer position

    ABuffer = []
    for i in range(b_max):
        ABuffer.append(0)

    def loopWork(self):
        """ Loop being executed in parallel. Wait for the Start command before starting new acquisitions"""
        while 1:
            if self.emparelhado == False:
                self.atualizeListPorts.emit(serial.tools.list_ports.comports())
            else:
                if self.measurementStart == False:
                    pass
                else:
                    if self.mode == 'COUNTER':
                        self.counterMode()
                    elif self.mode == 'BOXCAR':
                        self.boxcarMode()
                    else:
                        pass

    def setParams(self, tempoInt, largura, nAmostras, nRep, mode):
        """ Emits the acquisition parameters to the device """
        self.tempoInt = tempoInt
        self.largura = largura
        self.nAmostras = nAmostras
        self.nRep = nRep
        if mode == 'COUNTER':
            self.mode = mode
            self.nMode = 0
        if mode == 'BOXCAR':
            self.mode = mode
            self.nMode = 1
        try:
            self.ser.reset_output_buffer()
            self.ser.write(str("setparam("+str(self.tempoInt)+","+str(self.largura)+","+str(self.nAmostras)+","+str(self.nRep)+","+str(self.nMode)+")").encode('utf-8'))
        except Exception as erro:
            self.finish()
            self.measurementAbort.emit()
            x = erro.args[0]
            self.parent.label_relat.setText(x)

    def boxcarMode(self):
        """ Read and process the data sent by the device in Boxcar mode """
        A = []
        try:
            #self.ser.reset_input_buffer()
            a = self.ser.readline()
            self.entryLine = a.decode('utf-8')
            if self.entryLine[0] != "s":
                if self.entryLine[0] == 'B':#B: BOXCAR ; A: COUNTER
                    for i in self.entryLine[1:-3].split(","):
                        A.append(float(i))
                    self.atualizeData.emit(0,A,'BOXCAR')
            else: #No caso de acabarem as medidas
                self.finish()
                self.measurementAbort.emit()

        except Exception as erro:
            self.measurementAbort.emit()
            x = erro.args[0]
            self.parent.label_relat.setText(x)

    def counterMode(self):
        """ Read and process the data sent by the device in Counter mode """
        A = 0
        try:
            a = self.ser.readline()
            self.ser.flush()
            self.entryLine = a.decode('utf-8')

            if self.entryLine[0] == 'A':
                A = float(self.entryLine[1:])
            if self.b_pos < self.b_max-1:#Buffer circular
                self.ABuffer[self.b_pos] = A
                self.b_pos+=1
            else:
                self.b_pos = 0
            self.atualizeData.emit(self.b_pos,self.ABuffer,'COUNTER')
        except Exception as erro:
            self.finish()
            self.measurementAbort.emit()
            x = erro.args[0]
            self.parent.label_relat.setText(x)

    def finish(self):
        """ Reset input and output buffers """
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.b_pos = 0

class Main(QtWidgets.QMainWindow, layout_form):
    """ Thread responsible by the user interface """
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self,parent)
        self.setupUi(self)
        ##### INITIAL PROPERTIES #####
        self.tempoInt = 1000
        self.largura = 10
        self.nAmostras = 100
        self.nRep = 100
        self.mode = 'COUNTER'
        #Serial Related
        self.boudRate = 9600
        self.emparelhado = False
        self.listPorts = serial.tools.list_ports.comports()
        for i in range(len(self.listPorts)):
            self.comboBox_portaSerial.addItem(self.listPorts[i].description, self.listPorts[i].name)
        #Plot
        self.mainToolbar = self.addToolBar("Plot")
        self.plot = Plot(self.widget_plot, self.mainToolbar)

        ##### WIDGET ACTIONS #####
        #SpinBoxes
        self.spinBox_tempoInt.valueChanged.connect(self.changeParams)
        self.spinBox_janelaInt.valueChanged.connect(self.changeParams)
        self.spinBox_nAmostras.valueChanged.connect(self.changeParams)
        self.spinBox_nRepet.valueChanged.connect(self.changeParams)
        #~Buttons
        self.pushButton_comandar.clicked.connect(self.measurementStart)
        self.pushButton_emparelhar.clicked.connect(self.verificarSerial)
        self.pushButton_salvar.clicked.connect(self.saveFile)
        self.pushButton_abrir.clicked.connect(self.openFile)
        self.pushButton_regrAjustar.clicked.connect(self.regrRun)
        #~ComboBox
        self.comboBox_portaSerial.activated.connect(self.changeSerialParams)
        self.comboBox_modoOperacao.activated.connect(self.changeParams)
        ##### THREADS SETTINGS #####
        #Initial Settings
        self.rotinas = Worker()
        self.rotinas.parent = self
        self.executionThread = QtCore.QThread()
        self.rotinas.moveToThread(self.executionThread)
        self.executionThread.started.connect(self.rotinas.loopWork)
        self.executionThread.start()
        #Thread Signals
        self.rotinas.measurementAbort.connect(self.measurementAbort)
        self.rotinas.atualizeListPorts.connect(self.updateListPorts)
        self.rotinas.atualizeData.connect(self.atualizeData)


    ##### FUNCTIONS #####
    ##INTERFACE
    def atualizeData(self, i, a_list, mode):
        """ Atualize the data in the interface """
        if mode == 'COUNTER':
            #i: position of the last value on buffer
            self.lcdNumber_contA.display(a_list[i-1])
            self.plot.setData([np.arange(0,len(a_list)*self.tempoInt,self.tempoInt),a_list])
            self.label_relat.setText(str(i))
        if mode == 'BOXCAR':
            if len(a_list) != 0:
                self.lcdNumber_contA.display(a_list[0])
            self.plot.setData([np.arange(0,len(a_list)*self.largura,self.largura),a_list])

    def lockInterface(self, disabled = False):
        """ Lock/Unlock interface buttons during acquisition"""
        #~pushButtons
        self.pushButton_emparelhar.setDisabled(disabled)
        self.pushButton_salvar.setDisabled(disabled)
        self.pushButton_abrir.setDisabled(disabled)
        self.pushButton_regrParams.setDisabled(disabled)
        self.pushButton_regrAjustar.setDisabled(disabled)
        #~SpinBoxes
        self.spinBox_tempoInt.setDisabled(disabled)
        self.spinBox_janelaInt.setDisabled(disabled)
        self.spinBox_nAmostras.setDisabled(disabled)
        self.spinBox_nRepet.setDisabled(disabled)
        #ComboBox
        self.comboBox_modoOperacao.setDisabled(disabled)
        #RadioButtons
        self.radioButton_regrLinear.setDisabled(disabled)
        self.radioButton_regrExp.setDisabled(disabled)


    def changeParams(self):
        """ When the input values are changed, atualize the variables"""
        self.tempoInt = self.spinBox_tempoInt.value()
        self.largura = self.spinBox_janelaInt.value()
        self.nAmostras = self.spinBox_nAmostras.value()
        self.nRep = self.spinBox_nRepet.value()
        self.mode = self.comboBox_modoOperacao.currentText()
        self.label_relat.setText("Ao inciar, os parâmetros serão alterados")

        seconds = 2*(self.largura * self.nAmostras * self.nRep)/(1000000) #2* -> fator de conversão 13/03/2020
        hours, rem = divmod(seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        time = "{:0>2}:{:0>2}:{:0>2}"
        self.label_time.setText("Tempo Estimado:" + str(time).format(int(hours),int(minutes),seconds))

    #MEDIÇÃO
    def measurementStart(self):
        """Start/Abort measurement depending on the button state"""
        if self.pushButton_comandar.isChecked() == True:
            self.lockInterface(True)
            #self.plot.clearData()
            self.pushButton_comandar.setStyleSheet("background-color: rgb(255, 170, 127);")
            self.pushButton_comandar.setText("Abortar Experimento")
            self.rotinas.ser.reset_input_buffer()
            self.rotinas.ser.reset_output_buffer()
            time.sleep(0.5)
            self.rotinas.setParams(self.tempoInt, self.largura, self.nAmostras, self.nRep, self.mode)
            time.sleep(0.5)
            self.rotinas.measurementStart = True
            self.label_relat.setText("Experimento em andamento")
        else:
            self.measurementAbort()

    def measurementAbort(self):
        """Abort measurement routine"""
        self.rotinas.measurementStart = False
        self.rotinas.finish()
        time.sleep(0.5)
        self.lockInterface(False)
        self.pushButton_comandar.setChecked(False)
        self.pushButton_comandar.setStyleSheet("background-color: rgb(170, 255, 127);")
        self.pushButton_comandar.setText("Iniciar Experimento")
        self.label_relat.setText("Experimento encerrado")

    #COMUNICAÇÃO SERIAL
    def changeSerialParams(self):
        """ If the serial params are changes, do not allow communication before pairing"""
        self.pushButton_emparelhar.setDisabled(False)
        self.pushButton_comandar.setDisabled(True)
        self.comboBox_modoOperacao.setDisabled(True)

    def verificarSerial(self):
        """ Checks if the selected device can be suscessfully paired (if unpaired) """
        #conectar ou desconectar, dependendo do estado do botão
        if  self.pushButton_emparelhar.isChecked() == True:
            if self.comboBox_portaSerial.currentText() != 'None':
                portIndex = self.comboBox_portaSerial.currentIndex()
                self.boudRate = self.spinBox_boudRate.value()
                try:
                    self.rotinas.ser = serial.Serial(self.listPorts[portIndex].device, self.boudRate)
                    self.emparelhado = True
                    self.rotinas.emparelhado = True
                    self.label_relat.setText("Dispositivo emparelhado com sucesso")
                    self.pushButton_emparelhar.setText("Desconectar")
                    self.lockInterfaceParams(False)
                except Exception as erro:
                    self.pushButton_emparelhar.setChecked(False)
                    errorMessage =  erro.args[0]
                    self.label_relat.setText(errorMessage)
        else:
            self.emparelhado = False
            self.rotinas.emparelhado = False
            self.label_relat.setText("Dispositivo desconectado")
            self.pushButton_emparelhar.setText("Emparelhar")
            self.lockInterfaceParams(True)
            self.rotinas.ser.close()

    def lockInterfaceParams(self, disabled = False):
        """ Disables some interface commands during scan acquisitions """
        self.pushButton_comandar.setDisabled(disabled)
        self.comboBox_modoOperacao.setDisabled(disabled)
        self.comboBox_portaSerial.setDisabled(not disabled)
        #~SpinBoxes
        self.spinBox_tempoInt.setDisabled(disabled)
        self.spinBox_janelaInt.setDisabled(disabled)
        self.spinBox_nAmostras.setDisabled(disabled)
        self.spinBox_nRepet.setDisabled(disabled)

    def updateListPorts(self, newListPorts):
        """ Updates the list of available devices """
        if self.listPorts != newListPorts:
            self.listPorts = newListPorts
            self.comboBox_portaSerial.clear()
            for i in range(len(self.listPorts)):
                self.comboBox_portaSerial.addItem(self.listPorts[i].description)
        else:
            pass

    #ARQUIVOS
    def saveFile(self):
        """ Saves a .bxc file containing all informations from the measurement. Also saves a .png of the curve plot, and the raw data """
        if self.lineEdit_registro.text() != '':
            self.parameters = {
                "notes": self.textEdit.toHtml(),
                "tempoInt": self.tempoInt,
                "largura": self.largura,
                "nAmostras": self.nAmostras,
                "nRep": self.nRep,
                "boudRate": self.boudRate,
                "data": self.plot.getData(),
            }
            fileName, _ = QtWidgets.QFileDialog.getSaveFileName(self,"Select File Path",self.lineEdit_registro.text(),"Digital BoxCar (*.bxc)")
            if fileName:
                #Arquivo completo
                try:
                    file = open(fileName, 'wb')
                    pickle.dump(self.parameters, file)
                    file.close()
                    #Arquivos auxiliares
                    self.plot.plot.save_widget(fileName+'.png')
                    np.savetxt(fileName+'.txt', np.transpose(self.parameters["data"]), fmt='%.0f', delimiter="\t")
                    self.label_relat.setText("Arquivos salvos com sucesso")
                except:
                    self.label_relat.setText("Erro ao salvar arquivos")


    def openFile(self):
        """ Opens a .bxc file and updates the informations of the measurement. """
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self,"Select File Path","","Digital BoxCar (*.bxc)")
        if fileName:
            file = open(fileName, 'rb')
            self.parameters = pickle.load(file)
            file.close()
            #Setting the parameters in the current variables
            self.textEdit.setHtml(self.parameters["notes"])
            self.spinBox_tempoInt.setValue(self.parameters["tempoInt"])
            self.spinBox_janelaInt.setValue(self.parameters["largura"])
            self.spinBox_nAmostras.setValue(self.parameters["nAmostras"])
            self.spinBox_nRepet.setValue(self.parameters["nRep"])
            self.spinBox_boudRate.setValue(self.parameters["boudRate"])
            self.plot.setData(self.parameters["data"])
            #Defines Params
            self.changeParams()

    #ANALISIS - NOT IMPLEMENTED YET
    def regrRun(self):
        pass


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Main()
    window.show()
    app.exec_()
