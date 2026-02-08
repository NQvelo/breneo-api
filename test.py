from app.models import Job, Skill
s = Skill.objects.create(name="python")    # skill
j = Job.objects.create(
    title="Backend Developer",
    description="test job",
    salary_min=1000,
    salary_max=2000,
    time_to_ready="3 months"
)
j.required_skills.add(s)
j.id