import re
import os

files_to_patch = [
    "backend/api/routers/rpg_combat.py",
    "backend/db/crud/rpg/dungeon_core.py",
    "frontend/js/rpg_modules/04_arena_physics.js",
    "frontend/js/rpg_modules/05_player_skills.js"
]

for filepath in files_to_patch:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Python files
        content = re.sub(r'1\.42 \*\* max', '1.18 ** max', content)
        content = re.sub(r'1\.28 \*\* max', '1.18 ** max', content)
        content = re.sub(r'1\.23 \*\* max', '1.15 ** max', content)
        content = re.sub(r'1\.26 \*\* max', '1.18 ** max', content)
        
        # JS files
        content = re.sub(r'Math\.pow\(1\.28,', 'Math.pow(1.18,', content)
        content = re.sub(r'Math\.pow\(1\.23,', 'Math.pow(1.15,', content)

        # Fix random boss spawn in rpg_combat.py
        if "rpg_combat.py" in filepath:
            content = content.replace("target_template = random.choice(DOTA_FLOOR_BOSSES)", 
                                      "target_template = DOTA_FLOOR_BOSSES[min(len(DOTA_FLOOR_BOSSES) - 1, max(0, floor - 1))]")
            content = content.replace("DOTA_FLOOR_BOSSES", "NATAR_FLOOR_BOSSES")
            content = content.replace("DOTA_CREEPS_POOL", "NATAR_CREEPS_POOL")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
