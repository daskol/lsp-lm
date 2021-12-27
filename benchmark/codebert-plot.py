import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# Load measuremens.
df = pd.read_csv('timings.csv')
df['mean'] = df.measure.str.split(' ', 1, expand=True)[0].astype(int)
df['std'] = df.measure.str.rsplit(' ', 2, expand=True)[1].astype(float)
print(df)

# Assign color to execution framework.
colors_it = plt.rcParams['axes.prop_cycle'].by_key()['color']
tf_color = colors_it[0]
tf = df[:2]
pt_color = colors_it[1]
pt = df[2:3]
onnx_color = colors_it[2]
onnx = df[3:]
colors = ([tf_color] * len(tf) + [pt_color] * len(pt) +
          [onnx_color] * len(onnx))

# Prepare labels for bars.
labels = df.text.tolist()
labels[0] = 'Default'
labels[1] = 'w/ JIT'
labels[2] = 'Default'
for i in range(3, len(df)):
    labels[i] = labels[i].removeprefix('ONNX ')

# Render figure to file
fig, ax = plt.subplots(dpi=300, figsize=(8, 6))
plt.subplots_adjust(bottom=0.3)

tf_handle = mpl.patches.Patch(color=tf_color, label='TensorFlow')
pt_handle = mpl.patches.Patch(color=pt_color, label='PyTorch')
onnx_handle = mpl.patches.Patch(color=onnx_color, label='ONNX')

ax.legend(handles=[tf_handle, pt_handle, onnx_handle])
ax.grid(axis='y')
ax.bar(x=np.arange(len(df)),
       height=df['mean'].values,
       yerr=df['std'].values,
       color=colors)
ax.set_ylabel('Wall Time, ms')
ax.set_xticks(np.arange(len(df)))
ax.set_xticklabels(labels, rotation='vertical')

fig.suptitle('Execution time for different execution backends on CPU.')
fig.savefig('codebert-report.png')
