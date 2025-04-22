import os

processed_path = "data/events_processed"
filtered_path = "data/events_filtered/llama3.2_3b"
processed_total = 0
filtered_total = 0

for filename in os.listdir(processed_path):
    processed_file = os.path.join(processed_path, filename)
    filtered_file = os.path.join(filtered_path, filename)

    if os.path.exists(filtered_file):
        with open(processed_file, 'r', encoding='utf-8') as f1:
            lines_processed = sum(1 for _ in f1)

        with open(filtered_file, 'r', encoding='utf-8') as f2:
            lines_filtered = sum(1 for _ in f2)
        
        processed_total = processed_total + lines_processed
        filtered_total = filtered_total + lines_filtered
        print(f"{filename}: {lines_processed} -> {lines_filtered}")
    else:
        print(f"{filename}: arquivo correspondente não encontrado em events_filtered.")

print(f"{processed_total} -> {filtered_total}")