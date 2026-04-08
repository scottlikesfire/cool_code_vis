import random
import shutil
import sys
import time

import asciichartpy as acp


def make_random_walk(length=120):
    arr = [round(random.random() * 15)]
    for _ in range(1, length):
        step = round(random.random() * (2 if random.random() > 0.5 else -2))
        arr.append(arr[-1] + step)
    return arr


def main(duration=0, step_delay=0.05):
    length = 120
    arr1 = make_random_walk(length)
    arr2 = make_random_walk(length)
    arr3 = make_random_walk(length)
    arr4 = make_random_walk(length)

    colors = [acp.blue, acp.green, acp.default, acp.red]
    color_codes = ["\033[34m", "\033[32m", "\033[0m", "\033[31m"]
    reset = "\033[0m"

    config = {"colors": colors}

    step_delay = float(step_delay)
    arrays = [arr1, arr2, arr3, arr4]

    def build_legend(num_series):
        parts = []
        for j in range(num_series):
            parts.append(f"{color_codes[j]}■ sample_{j}{reset}")
        return "  ".join(parts)

    def add_y_label(chart):
        lines = chart.split("\n")
        label = "baseline performance"
        # Center the label vertically alongside the chart
        pad_top = (len(lines) - len(label)) // 2
        result = []
        for idx, line in enumerate(lines):
            label_idx = idx - pad_top
            if 0 <= label_idx < len(label):
                result.append(label[label_idx] + " " + line)
            else:
                result.append("  " + line)
        return "\n".join(result)

    term_width = shutil.get_terminal_size().columns
    x_label = "generation number"
    x_padding = max(0, (term_width - len(x_label)) // 2)

    # Animate one series at a time, layering on top of each other
    for series_idx in range(len(arrays)):
        series_config = {"colors": config["colors"][:series_idx + 1]}
        for i in range(1, length + 1):
            # Completed series shown in full, current series grows
            plot_data = [arr[:length] for arr in arrays[:series_idx]]
            plot_data.append(arrays[series_idx][:i])
            chart = acp.plot(plot_data, series_config)
            chart = add_y_label(chart)
            legend = build_legend(series_idx + 1)
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.write(chart + "\n" + " " * x_padding + x_label + "\n\n  " + legend + "\n")
            sys.stdout.flush()
            time.sleep(step_delay)

    # Hold the final chart for duration seconds
    if duration:
        time.sleep(float(duration))


if __name__ == "__main__":
    main()
