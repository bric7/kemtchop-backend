#!/usr/bin/env python3
"""Vérifie que toutes les dépendances de requirements.txt sont installées"""
import sys
from importlib.metadata import version, PackageNotFoundError

def check_requirements(filepath="requirements.txt"):
    with open(filepath, 'r') as f:
        packages = []
        for line in f:
            line = line.split('#')[0].strip()  # Enlever commentaires
            if line and not line.startswith('-'):  # Ignorer lignes vides et flags pip
                # Extraire le nom du package (enlever [extra], ==version, >=, etc.)
                name = line.split('[')[0].split('==')[0].split('>=')[0].split('<=')[0].strip()
                if name:
                    packages.append(name)
    
    missing = []
    for pkg in packages:
        try:
            version(pkg)  # Vérifie si le package est installé
        except PackageNotFoundError:
            missing.append(pkg)
    
    if missing:
        print(f"❌ Dépendances manquantes : {', '.join(missing)}")
        print(f"💡 Installe-les avec : pip install {' '.join(missing)}")
        return False
    
    print(f"✅ Toutes les {len(packages)} dépendances sont installées")
    return True

if __name__ == "__main__":
    # Déterminer le chemin de requirements.txt (supporte exécution depuis scripts/)
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    req_path = os.path.join(project_root, "requirements.txt")
    
    if not os.path.exists(req_path):
        print(f"❌ requirements.txt non trouvé à {req_path}")
        sys.exit(1)
    
    success = check_requirements(req_path)
    sys.exit(0 if success else 1)