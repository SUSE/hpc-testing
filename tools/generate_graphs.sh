#!/bin/bash

# Get the list of CSV files
files=("$@")
if [ ${#files[@]} -eq 0 ]; then
    echo "Usage: $0 <file1.csv> <file2.csv> ..."
    exit 1
fi

# Get the number of lines from the first CSV file (assuming all are the same)
num_lines=$(wc -l < "${files[0]}")

# Loop through each data line (each test), skipping the header
for i in $(seq 2 $num_lines); do
    
    # Get the test name and unit from the first file for the current line.
    # This will be used for the graph title and axis labels.
    line_info=$(awk -F, "NR==$i {print \$1 \"|\" \$2}" "${files[0]}")
    test_name=$(echo "$line_info" | cut -d'|' -f1)
    unit=$(echo "$line_info" | cut -d'|' -f2)

    # Arrays to hold plot commands and temporary data files
    plot_parts=()
    temp_files=()

    # Inner loop through each CSV file to build the curves for the current test.
    for file in "${files[@]}"; do
        # Get header for sizes
        header=$(head -n 1 "$file")
        IFS=',' read -r -a sizes <<< "$header"

        # Get the specific data line
        line_data=$(awk "NR==$i" "$file")
        IFS=',' read -r -a values <<< "$line_data"

        # Create a temporary file for this curve's data
        tmp_datafile="tmp_$(echo "$file" | sed -e 's/\//_/g')_${i}.dat"
        rm -f "$tmp_datafile"

        # Write the data (size and value) to the temporary file
        for j in $(seq 2 $((${#values[@]} - 1))); do
            # Skip empty values and ensure both size and value exist
            if [ -n "${sizes[$j]}" ] && [ -n "${values[$j]}" ]; then
                echo "${sizes[$j]} ${values[$j]}" >> "$tmp_datafile"
            fi
        done
        
        # Add this curve to the plot command parts array
        plot_parts+=("'$tmp_datafile' using 1:2 with linespoints title '$file'")
        temp_files+=("$tmp_datafile")
    done

    # Join the plot parts with commas for the final gnuplot command
    plot_command=$(IFS=,; echo "${plot_parts[*]}")

    # Determine if y-axis should be log scale
    logscale_y=""
    if [ "$unit" == "t_avg[usec]" ]; then
        logscale_y="set logscale y"
    fi

    # Generate the plot using gnuplot
    gnuplot <<- EOF
        set terminal svg enhanced size 2000 1000 font 'Verdana,10' background rgb 'white'
        set output "${test_name}.svg"
        set title "${test_name}"
        set xlabel "Size (bytes)"
        set ylabel "${unit}"
        set key outside
        set logscale x 2
        $logscale_y
        plot $plot_command
EOF

    # Clean up the temporary files
    rm -f "${temp_files[@]}"
done

echo "Graph generation complete."
