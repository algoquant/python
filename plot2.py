import matplotlib.pyplot as plt
plt.ion()

fig, (ax1, ax2) = plt.subplots(1, 2) # 1 row, 2 columns of subplots

ax1.plot([1, 2, 3], [4, 5, 6])
ax1.set_title("Subplot A")

ax2.hist([1, 2, 2, 3, 3, 3])
ax2.set_title("Subplot B")
