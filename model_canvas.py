
import Tkinter as tk
import ttk
import itertools as it

from model import Model
#from model_canvas_operation import MCO_Move
#from particle import DrawnParticle
#import grid
#import utils
#import Operation
#from brush import Brush
#from copy import deepcopy
from model_canvas_layer import ViewLayer, EditBackgroundLayer

sticky_all = tk.N + tk.S + tk.E + tk.W

#MOD_SHIFT = 0x1
#MOD_CTRL = 0x4
#MOD_BTN1 = 0x100
#MOD_LEFTALT = 0x0008  

class ModelCanvas(tk.Canvas, object):
  def __init__(self, master, model = None, mode = 'view', **kargs):
    tk.Canvas.__init__(self, master, bd = 0, highlightthickness = 0, takefocus=1, **kargs)

    self._model = model

    self._layers = []

    if mode == 'edit':
      self._layers.append(EditBackgroundLayer(self))
    elif mode == 'view':
      self._layers.append(ViewLayer(self))
    else:
      assert False, 'Unsupported mode: {0}'.format(mode)
    self.top_layer().start()

  @property
  def model(self):
    return self._model
  
  def set_model(self, model):
    self.background_layer().set_model(model)

  def top_layer(self):
    return self._layers[-1]
  def background_layer(self):
    return self._layers[0]
  def push_layer(self, layer):
    self._layers.append(layer)
  def pop_layer(self):
    return self._layers.pop()

  def start_layer(self, layer):
    self.top_layer().pause()
    self.push_layer(layer)
    self.top_layer().start()
  def merge_top_layer(self):
    layer = self.pop_layer()
    layer.finish()
    self.top_layer().merge(layer)
    layer.clean()
    self.top_layer().resume()
  def cancel_top_layer(self):
    layer = self._layers.pop()
    layer.cancel()
    layer.clean()
    self.top_layer().resume()

  def update_layer(self, layer):
    self.after_idle(layer.update)
    #print 'update requested:', layer



