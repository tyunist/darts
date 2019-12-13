import numpy as np 
import os, csv 
import matplotlib.pyplot as plt 

DATASET = "imagewoof2"

folder = "./eval-imagewoof2dataset-4layers-sgd-1.0E-07adap_d-1.0E-09lr-EXP-20191210-221620"
train_colors = ["b", "b"]
val_colors   = ["0.5", "0.5"]

line_types   = ["solid", "dotted"]

def plot(train_mat, val_mat, plot_legends, figure_file):
    #, plot_colors, plot_markers, plot_legends, min_time):
    plt.rc('font', family='serif')
    plt.rc('xtick', labelsize='medium', )
    plt.rc('ytick', labelsize='medium')
    plt.rc('legend', fontsize='large')
    plt.rc('axes', labelsize='large')
    plt.rc('text', usetex=False)
    plt.rc('figure', figsize=(6,5))

    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    
    x_axis = range(len(train_mat[0]))
    for i in range(len(train_mat)):
        ax.plot(x_axis, train_mat[i], color=train_colors[i], ls=line_types[i])
        ax.plot(x_axis, val_mat[i],   color=val_colors[i],   ls=line_types[i])

    ax.set_xlabel('Epochs')
    ax.set_ylabel('{} Accuracy (%)'.format(DATASET))
    
    ax.legend(plot_legends)
    plt.tight_layout()
    plt.savefig(figure_file, format="eps", dpi=1000)
    plt.show()


def main():
    logfile = folder + "/log.txt"
    savefig_file = folder + "/plot_results.eps"
    train_top1_list = [] 
    train_top5_list = [] 
    train_acc_list  = [] 
    
    val_top1_list = [] 
    val_top5_list = [] 
    val_acc_list  = [] 

    with open(logfile, "r") as f:
        line = f.readline()
        line_count = 1
        while line:
            line = f.readline()
            valid_key = "valid 150" if DATASET == "CIFAR-10" else "valid 050"
            if(valid_key in line):
                line = line.split(" ")
                print(line)
                val_top5 = float(line[-1]) 
                val_top1 = float(line[-2]) 
                val_acc  = float(line[-3])
                print("Val top 1: %.4f"%val_top1)
                print("Val top 5: %.4f"%val_top5)
                print("Val acc  : %.4f"%val_acc)
                val_top1_list.append(val_top1)
                val_top5_list.append(val_top5)
                val_acc_list.append(val_acc)
            train_key = "train 750" if DATASET == "CIFAR-10" else "train 100"
            if(train_key in line):
                line = line.split(" ")
                print(line)
                train_top5 = float(line[-1]) 
                train_top1 = float(line[-2]) 
                train_acc  = float(line[-3])
                print("Train top 1: %.4f"%train_top1)
                print("Train top 5: %.4f"%train_top5)
                print("Train acc  : %.4f"%train_acc)
                train_top1_list.append(train_top1)
                train_top5_list.append(train_top5)
                train_acc_list.append(train_acc)
            line_count += 1
        
    # Finish reading
    print("--------------------------------")
    print("Finish reading %d lines"%line_count)

    plot([train_top1_list, train_top5_list], [val_top1_list, val_top5_list], ["train_top1", "val_top1", "train_top5", "val_top5"], savefig_file)


if __name__=="__main__":
    main()
