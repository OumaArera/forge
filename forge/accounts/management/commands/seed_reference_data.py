"""
Seed the reference data a new FORGE instance needs to be usable.

Idempotent: safe to run repeatedly. Schools and programmes here are taken from
the University's published offering and should be checked against the
Registrar's current list before a pilot launch.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from forge.accounts.models import DisciplineArea, Programme, School, Skill
from forge.community.models import Space
from forge.recognition.models import Badge, Level

SCHOOLS = [
    ("School of Science and Technology", "SST"),
    ("School of Business and Economics", "SBE"),
    ("School of Education", "SED"),
    ("School of Health Sciences", "SHS"),
    ("School of Social Sciences and Humanities", "SSH"),
    ("School of Agriculture and Environmental Sciences", "SAE"),
]

PROGRAMMES = [
    ("SST", "BSc. Cyber Security and Digital Forensics", "BSC-CSDF", "undergraduate"),
    ("SST", "BSc. Computer Science", "BSC-CS", "undergraduate"),
    ("SST", "BSc. Information Technology", "BSC-IT", "undergraduate"),
    ("SST", "BSc. Data Science", "BSC-DS", "undergraduate"),
    ("SBE", "Bachelor of Commerce", "BCOM", "undergraduate"),
    ("SBE", "BSc. Economics", "BSC-ECON", "undergraduate"),
    ("SED", "Bachelor of Education (Arts)", "BED-ARTS", "undergraduate"),
    ("SED", "Bachelor of Education (Science)", "BED-SCI", "undergraduate"),
    ("SHS", "Bachelor of Science in Nursing", "BSN", "undergraduate"),
    ("SHS", "Bachelor of Public Health", "BPH", "undergraduate"),
    ("SSH", "Bachelor of Public Administration", "BPA", "undergraduate"),
    ("SSH", "Bachelor of Public Communication", "BPC", "undergraduate"),
    ("SAE", "BSc. Agri-Technology", "BSC-AGT", "undergraduate"),
]

# Discipline areas are deliberately not the same as schools: a project on
# digital learning material for a rural clinic is Health and Education at once.
DISCIPLINE_AREAS = [
    ("Software and Systems", 10, "Building and running software."),
    ("Cyber Security", 20, "Defensive security, forensics and assurance."),
    ("Data and Analytics", 30, "Data collection, analysis and visualisation."),
    ("Health", 40, "Clinical practice, public health and health systems."),
    ("Education and Learning", 50, "Teaching, learning design and learning materials."),
    ("Business and Enterprise", 60, "Enterprise, finance and operations."),
    ("Agriculture and Environment", 70, "Farming, food systems and the environment."),
    ("Communication and Media", 80, "Public communication, media and design."),
    ("Governance and Public Service", 90, "Public administration and civic work."),
    ("Community and Platform", 100, "Work on FORGE itself and on the community."),
]

# Section 10.4 of the concept proposal: Apprentice through Builder and
# Craftsman to Master Builder, with the highest standing reserved for those
# who have both delivered and taught.
LEVELS = [
    ("Apprentice", 1, 0, 0, 0, False,
     "You have joined and begun. Everyone starts here."),
    ("Builder", 2, 60, 5, 1, False,
     "You have contributed consistently and seen a project through to delivery."),
    ("Craftsman", 3, 250, 20, 3, False,
     "Sustained, confirmed contribution across several delivered projects."),
    ("Master Builder", 4, 600, 45, 5, True,
     "Both delivered and taught. This level cannot be reached on output alone: "
     "it requires confirmed mentorship of other members."),
]

BADGES = [
    ("First delivery", "first-delivery", "milestone",
     "Saw a first project through to completion.",
     "Awarded when a project you contributed to reaches Completed."),
    ("Led to delivery", "led-to-delivery", "stewardship",
     "Led a project from proposal to completion.",
     "Awarded when a project you led reaches Completed."),
    ("Teacher", "teacher", "community",
     "Sustained mentorship of other members.",
     "Awarded at 20 confirmed points in the mentorship dimension."),
    ("Writes it down", "writes-it-down", "craft",
     "Sustained documentation work.",
     "Awarded at 20 confirmed points in the documentation dimension."),
    ("Crossed the aisle", "crossed-the-aisle", "community",
     "Contributed to a team drawn from more than one school.",
     "Awarded on a confirmed contribution to a cross-school team."),
]

SKILLS = [
    "Python", "JavaScript", "TypeScript", "Django", "React", "PostgreSQL",
    "Git", "Docker", "Linux", "REST APIs", "Testing", "Technical writing",
    "UI design", "UX research", "Figma", "Data analysis", "Statistics",
    "Machine learning", "Network security", "Digital forensics",
    "Incident response", "Penetration testing (lab only)", "Project management",
    "Facilitation", "Public speaking", "Field research", "Survey design",
    "Qualitative research", "Accounting", "Financial modelling",
    "Curriculum design", "Instructional video", "Clinical assessment",
    "Health education", "Agronomy", "GIS and mapping", "Mobile development",
    "Android", "Flutter", "Accessibility", "Translation and localisation",
]


class Command(BaseCommand):
    help = "Seed schools, programmes, discipline areas, levels, badges and skills."

    @transaction.atomic
    def handle(self, *args, **options):
        for name, code in SCHOOLS:
            School.objects.update_or_create(code=code, defaults={"name": name})
        self.stdout.write(f"  schools: {School.objects.count()}")

        for school_code, name, code, level in PROGRAMMES:
            school = School.objects.get(code=school_code)
            Programme.objects.update_or_create(
                code=code, defaults={"name": name, "school": school, "level": level})
        self.stdout.write(f"  programmes: {Programme.objects.count()}")

        for name, order, description in DISCIPLINE_AREAS:
            DisciplineArea.objects.update_or_create(
                slug=slugify(name),
                defaults={"name": name, "display_order": order,
                          "description": description})
        self.stdout.write(f"  discipline areas: {DisciplineArea.objects.count()}")

        for area in DisciplineArea.objects.all():
            Space.objects.update_or_create(
                slug=area.slug,
                defaults={"name": area.name, "discipline_area": area,
                          "description": area.description,
                          "display_order": area.display_order})
        Space.objects.update_or_create(
            slug="general",
            defaults={"name": "General", "display_order": 1,
                      "description": "Anything that does not belong elsewhere."})
        self.stdout.write(f"  community spaces: {Space.objects.count()}")

        for name, rank, points, contributions, projects, teaching, description in LEVELS:
            Level.objects.update_or_create(
                rank=rank,
                defaults={"name": name, "slug": slugify(name), "min_points": points,
                          "min_confirmed_contributions": contributions,
                          "min_completed_projects": projects,
                          "requires_teaching": teaching, "description": description})
        self.stdout.write(f"  levels: {Level.objects.count()}")

        for name, slug, kind, description, criteria in BADGES:
            Badge.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "kind": kind, "description": description,
                          "criteria": criteria})
        self.stdout.write(f"  badges: {Badge.objects.count()}")

        for name in SKILLS:
            Skill.objects.update_or_create(
                slug=slugify(name)[:80], defaults={"name": name, "is_approved": True})
        self.stdout.write(f"  skills: {Skill.objects.count()}")

        self.stdout.write(self.style.SUCCESS("\nReference data seeded."))
        self.stdout.write(self.style.WARNING(
            "Check the school and programme lists against the Registrar's current "
            "offering before a pilot launch."
        ))
