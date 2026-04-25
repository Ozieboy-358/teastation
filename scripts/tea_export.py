import sqlite3
import yaml
import os

# Set up paths
base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(os.path.dirname(base_dir), 'data', 'tea_station.db')
output_file = os.path.join(os.path.dirname(base_dir), 'data', 'tea_station.yaml')

def export_to_docker_style():
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tea")
        rows = cursor.fetchall()

        docker_style_data = {}

        for row in rows:
            # Clean name for YAML key
            key_name = str(row['name']).lower().replace(" ", "_").replace("(", "").replace(")", "").replace("'", "")

            docker_style_data[key_name] = {
                "container_name": key_name,
                "category": row['category'],
                "environment": [
                    f"RATIO={row['ratio']}",
                    f"TEMP={row['temp']}",
                    f"TIME={row['time']}",
                    f"BREW_COUNT={row['brew_count']}"
                ],
                "image": f"tea_station/{row['category'].lower().replace(' ', '_')}:latest",
                "notes": row['notes'],
                "volumes": [
                    f"additive:/{row['additions']}",
                    f"snack:/{row['snack']}"
                ],
                "restart": "unless-stopped"
            }

        final_output = {
            "version": "3.8",
            "services": docker_style_data
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(final_output, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

        conn.close()
        print(f"✅ Successfully exported {len(rows)} teas to {output_file}")

    except Exception as e:
        print(f"❌ Export failed: {e}")

if __name__ == "__main__":
    export_to_docker_style()
