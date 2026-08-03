"""
The comp set: every property scraped each run, and which parser in scrape.py
handles its page. Add a competitor by adding an entry here plus a matching
parser function - see README.md "Adding another competitor".
"""

PROPERTIES = [
    {
        "id": "student_roost_st_mungos_ensuite",
        "name": "St Mungo's (Student Roost - our own) - En-suite",
        "url": "https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-ensuite-st-mungos",
        "is_own": True,
        "parser": "student_roost",
    },
    {
        "id": "student_roost_st_mungos_studio",
        "name": "St Mungo's (Student Roost - our own) - Studio",
        "url": "https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-studio-st-mungos",
        "is_own": True,
        "parser": "student_roost",
    },
    {
        "id": "abodus_st_james",
        "name": "St James (Abodus)",
        "url": "https://abodusstudents.com/accommodation/st-james-glasgow#the-rooms",
        "is_own": False,
        "parser": "abodus",
    },
    {
        "id": "prestige_foundry_courtyard",
        "name": "Foundry Courtyard (Prestige)",
        "url": "https://prestigestudentliving.com/student-accommodation/glasgow/foundry-courtyard",
        "is_own": False,
        "parser": "prestige",
    },
    {
        "id": "canvas_boyce_house",
        "name": "Boyce House (Canvas)",
        "url": "https://www.canvas-world.com/en/locations/united-kingdom/glasgow/boyce-house#rooms",
        "is_own": False,
        "parser": "canvas",
    },
]
