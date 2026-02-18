
import os

class FileClassifier:
    @staticmethod
    def classify_files(file_paths):
        """
        Classifies files based on keywords in their names.
        Returns a dictionary mapping file types to lists of file paths.
        """
        classified = {
            "FORTECH": [],
            "AS400": [],
            "NUMIA": [],
            "IP_CARTE": [],
            "IP_BUONI": [],
            "SATISPAY": [],
            "UNKNOWN": []
        }

        for path in file_paths:
            filename = os.path.basename(path).upper()
            
            if "FORTECH" in filename:
                classified["FORTECH"].append(path)
            elif "AS400" in filename:
                classified["AS400"].append(path)
            elif "NUMIA" in filename:
                classified["NUMIA"].append(path)
            elif "IPORTAL" in filename and "BUONI" in filename:
                classified["IP_BUONI"].append(path)
            elif "IPORTAL" in filename: # Assuming other IPORTAL is cards
                classified["IP_CARTE"].append(path)
            elif "SATISPAY" in filename:
                classified["SATISPAY"].append(path)
            else:
                classified["UNKNOWN"].append(path)
        
        return classified

    @staticmethod
    def validate_group(classified_files):
        """
        Checks if all required files are present.
        Returns a list of missing types and a boolean valid status.
        """
        required_types = ["FORTECH", "AS400", "NUMIA", "IP_CARTE", "IP_BUONI", "SATISPAY"]
        missing = []
        
        for r_type in required_types:
            if not classified_files[r_type]:
                missing.append(r_type)
        
        return missing, len(missing) == 0
