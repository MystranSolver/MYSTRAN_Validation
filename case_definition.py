
class CaseDefinition:
    def __init__(self):
        self.test_type = ""
        self.deck_filename = ""
        self.filter_string = ""
        self.operation = ""
        self.reference_value = 0.0
        self.comparison_type = "percent"
        self.tolerance = 0.0
        self.group_atol = {}
        self.knownfail = False

    def tolerance_suffix(self):
        return "%" if self.comparison_type == "percent" else ""        
