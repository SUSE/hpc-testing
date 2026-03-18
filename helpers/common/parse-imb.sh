#!/bin/bash

# Check for correct number of arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <input_log_file> <output_csv_file>"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="$2"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file '$INPUT_FILE' not found."
    exit 1
fi

# Process data
awk '
    # Set the test name
    /^# Benchmarking/ {
        test_name = $3
        mode = ""
        in_valid_test = 0
    }

    # Set the mode
    /MODE:/ {
        mode = "_" $3
    }

    # Process unit lines
    /^\s+#bytes/ {
        full_test_name = test_name mode
        data_types[full_test_name] = $NF
        in_valid_test = 1
    }
    # Process data lines
    /^\s*[0-9]+/ {
        if (!in_valid_test) next
        full_test_name = test_name mode

        # If we have not seen this test before, add it to our ordered list
        if (!(full_test_name in seen_tests)) {
            test_order[test_idx++] = full_test_name
            seen_tests[full_test_name] = 1
        }

        results[full_test_name, $1] = $NF
    }

    END {
        # Get all sizes and sort them
        for (r in results) {
            split(r, a, SUBSEP)
            sizes[a[2]] = 1
        }

        n = asorti(sizes, sorted_sizes, "@ind_num_asc")

        # Print header
        header = "Test_Name,Data_Type"
        for (j = 1; j <= n; j++) {
            header = header "," sorted_sizes[j]
        }
        print header

        # Print results in the order they were found
        for (i = 0; i < test_idx; i++) {
            test = test_order[i]
            if (data_types[test] == "")
               continue

            line = test "," data_types[test]
            for (j = 1; j <= n; j++) {
                size = sorted_sizes[j]
                line = line "," results[test, size]
            }
            print line
        }
    }
' "$INPUT_FILE" > "$OUTPUT_FILE"
