import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    t = int(input_data[0])
    idx = 1
    for _ in range(t):
        n = int(input_data[idx])
        k = int(input_data[idx + 1])
        idx += 2

        if k == 1:
            print(n)
            continue

        if k % 2 == 1:
            print(k * n)
            continue

        m = n.bit_length() - 1
        j = -1
        for bit in range(m - 1, -1, -1):
            if (n >> bit) & 1:
                j = bit
                break

        if j == -1:
            print((k - 1) * n)
        else:
            tail = 0
            for bit in range(j - 1, -1, -1):
                if not ((n >> bit) & 1):
                    tail |= (1 << bit)
            a = n - (1 << j) + tail
            b = (1 << j) + tail
        print((k - 2) * n + a + b)

solve()