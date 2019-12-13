import os
import sys
import time
import glob
import numpy as np
import torch
import utils
import logging
import argparse
import torch.nn as nn
import torch.utils
import torch.nn.functional as F
import torchvision.datasets as dset
import torch.backends.cudnn as cudnn

from torch.autograd import Variable
from model_search import Network
from architect import Architect

MAX_TIME = 40507

parser = argparse.ArgumentParser("imagewoof2")
parser.add_argument('--dataset_name', type=str, default='imagewoof2', help='name of the dataset')
parser.add_argument('--data', type=str, default='../data', help='location of the data corpus')
parser.add_argument('--img_h', type=int, default='128', help='image hight')
parser.add_argument('--img_w', type=int, default='128', help='image width')
parser.add_argument('--batch_size', type=int, default=16, help='batch size')
parser.add_argument('--learning_rate', type=float, default=0.025, help='init learning rate')
parser.add_argument('--learning_rate_min', type=float, default=0.001, help='min learning rate')
parser.add_argument('--momentum', type=float, default=0.9, help='momentum')
parser.add_argument('--weight_decay', type=float, default=3e-4, help='weight decay')
parser.add_argument('--report_freq', type=float, default=50, help='report frequency')
parser.add_argument('--gpu', type=int, default=0, help='gpu device id')
parser.add_argument('--epochs', type=int, default=100, help='num of training epochs')
parser.add_argument('--init_channels', type=int, default=16, help='num of init channels')
parser.add_argument('--layers', type=int, default=4, help='total number of layers')
parser.add_argument('--model_path', type=str, default='saved_models', help='path to save the model')
parser.add_argument('--cutout', action='store_true', default=False, help='use cutout')
parser.add_argument('--cutout_length', type=int, default=32, help='cutout length')
parser.add_argument('--drop_path_prob', type=float, default=0.3, help='drop path probability')
parser.add_argument('--save', type=str, default='EXP', help='experiment name')
parser.add_argument('--seed', type=int, default=2, help='random seed')
parser.add_argument('--grad_clip', type=float, default=5, help='gradient clipping')
parser.add_argument('--train_portion', type=float, default=0.5, help='portion of training data')
parser.add_argument('--unrolled', action='store_true', default=False, help='use one-step unrolled validation loss')
parser.add_argument('--arch_learning_rate', type=float, default=3e-4, help='learning rate for arch encoding')
parser.add_argument('--arch_weight_decay', type=float, default=1e-3, help='weight decay for arch encoding')
args = parser.parse_args()

args.save = 'search-{}datset-{}layers-{}'.format(args.dataset_name, args.layers, time.strftime("%Y%m%d-%H%M%S"))
utils.create_exp_dir(args.save, scripts_to_save=glob.glob('*.py'))

log_format = '%(asctime)s %(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
    format=log_format, datefmt='%m/%d %I:%M:%S %p')
fh = logging.FileHandler(os.path.join(args.save, 'log.txt'))
fh.setFormatter(logging.Formatter(log_format))
logging.getLogger().addHandler(fh)


num_classes_dict = {"imagewoof2": 10}
NUM_CLASSES = num_classes_dict[args.dataset_name]


def main():
  if not torch.cuda.is_available():
    logging.info('no gpu device available')
    sys.exit(1)

  np.random.seed(args.seed)
  torch.cuda.set_device(args.gpu)
  cudnn.benchmark = True
  torch.manual_seed(args.seed)
  cudnn.enabled=True
  torch.cuda.manual_seed(args.seed)
  logging.info('gpu device = %d' % args.gpu)
  logging.info("args = %s", args)

  criterion = nn.CrossEntropyLoss()
  criterion = criterion.cuda()
  # Model include alpha
  model = Network(args.init_channels, NUM_CLASSES, args.layers, criterion)
  model = model.cuda()
  total_params, total_trainable_params = utils.count_parameters_in_numels(model)
  logging.info("param size = %fMB", utils.count_parameters_in_MB(model))
  logging.info("param size = %f Mils with %f Mils trainable"%(total_params/1e6, total_trainable_params/1e6))

  optimizer = torch.optim.SGD(
      model.parameters(),
      args.learning_rate,
      momentum=args.momentum,
      weight_decay=args.weight_decay)
  
  traindir = os.path.join(args.data, args.dataset_name, "train")
  valdir   = os.path.join(args.data, args.dataset_name, "val")

  train_transform, valid_transform = utils._data_transforms_imagenet(args)
  train_data = dset.ImageFolder(root=traindir, transform=train_transform)
  val_data   = dset.ImageFolder(root=valdir, transform=train_transform)

  num_train = len(train_data)
  indices = list(range(num_train))
  split = int(np.floor(args.train_portion * num_train))

  train_queue = torch.utils.data.DataLoader(
      train_data, batch_size=args.batch_size,
      shuffle=True,
      pin_memory=True, num_workers=4)

  valid_queue = torch.utils.data.DataLoader(
      val_data, batch_size=args.batch_size,
      shuffle=False,
      pin_memory=True, num_workers=4)


  scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, float(args.epochs), eta_min=args.learning_rate_min)

  architect = Architect(model, args)
  
  start_time = time.time()

  for epoch in range(args.epochs):
    scheduler.step()
    lr = scheduler.get_lr()[0]
    train_time = time.time() - start_time 
    logging.info('[%.6fs]epoch %d lr %e', train_time, epoch, lr)
    if train_time > MAX_TIME:
      logging.info('-----------------------------------')
      logging.info('Max training time %.2f = MAX_TIME passed!')
      break

    genotype = model.genotype()
    logging.info('genotype = %s', genotype)
    tmp = F.softmax(model.alphas_normal, dim=-1).detach().cpu().numpy()
    normal_opt_selection_matrix = np.array2string(tmp, formatter={'float_kind':lambda tmp: "%.6f"%tmp})
    tmp = F.softmax(model.alphas_reduce, dim=-1).detach().cpu().numpy()
    reduce_opt_selection_matrix = np.array2string(tmp, formatter={'float_kind':lambda tmp: "%.6f"%tmp})
    #print(normal_opt_selection_matrix)
    #print(reduce_opt_selection_matrix)
    logging.info('Operation Selection Matrix:')
    logging.info('\n%s', normal_opt_selection_matrix)     
    logging.info('\n%s', reduce_opt_selection_matrix)     


    # training
    train_acc, train_obj = train(train_queue, valid_queue, model, architect, criterion, optimizer, lr)
    logging.info('train_acc %f', train_acc)

    # validation
    with torch.no_grad():
      valid_acc, valid_obj = infer(valid_queue, model, criterion)
    logging.info('valid_acc %f', valid_acc)

    utils.save(model, os.path.join(args.save, 'weights.pt'))


def train(train_queue, valid_queue, model, architect, criterion, optimizer, lr):
  objs = utils.AvgrageMeter()
  top1 = utils.AvgrageMeter()
  top5 = utils.AvgrageMeter()

  for step, (input, target) in enumerate(train_queue):
    model.train()
    n = input.size(0)

    input = Variable(input, requires_grad=False).cuda()
    target = Variable(target, requires_grad=False).cuda(async=True)

    # get a random minibatch from the search queue with replacement
    input_search, target_search = next(iter(valid_queue))
    input_search = Variable(input_search, requires_grad=False).cuda()
    target_search = Variable(target_search, requires_grad=False).cuda(async=True)
    
    architect.step(input, target, input_search, target_search, lr, optimizer, unrolled=args.unrolled)


    optimizer.zero_grad()
    logits = model(input)
    loss = criterion(logits, target)


    loss.backward()

    nn.utils.clip_grad_norm(model.parameters(), args.grad_clip)
    optimizer.step()

    prec1, prec5 = utils.accuracy(logits, target, topk=(1, 5))
    objs.update(loss.data, n)
    top1.update(prec1.data, n)
    top5.update(prec5.data, n)

    if step % args.report_freq == 0:
      logging.info('train %03d %e %f %f', step, objs.avg, top1.avg, top5.avg)

  return top1.avg, objs.avg


def infer(valid_queue, model, criterion):
  objs = utils.AvgrageMeter()
  top1 = utils.AvgrageMeter()
  top5 = utils.AvgrageMeter()
  model.eval()

  for step, (input, target) in enumerate(valid_queue):
    input = Variable(input, volatile=True).cuda()
    target = Variable(target, volatile=True).cuda(async=True)

    logits = model(input)
    loss = criterion(logits, target)

    prec1, prec5 = utils.accuracy(logits, target, topk=(1, 5))
    n = input.size(0)
    objs.update(loss.data, n)
    top1.update(prec1.data, n)
    top5.update(prec5.data, n)

    if step % args.report_freq == 0:
      logging.info('valid %03d %e %f %f', step, objs.avg, top1.avg, top5.avg)

  return top1.avg, objs.avg


if __name__ == '__main__':
  main() 
