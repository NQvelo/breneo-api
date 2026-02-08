from django.core.management.base import BaseCommand
import os ,joblib, random
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from app.models import User, UserSkill

class Command(BaseCommand):
    help = "Train ML model from user skills and save as model.pkl"

    def handle(self, *args, **options):
        # 💡 ყველა შესაძლებლობების მქონე უნარები
        all_skills = [
            "React.js", "Vue.js", "Angular", "Node.js", "Python", "Django",
            "SQL", "iOS", "Android", "React Native", "JavaScript",
            "UI/UX", "Product Designer", "Graphic Designer", "3D Modeler", "Content Creator","Team Player","Team Player","Efficient Planner",
            "Organized Worker","Leader / Manager","Project Manager","Curious Learner"
        ]
        possible_jobs = [
                "Frontend Developer",
                "Backend Developer",
                "iOS Developer",
                "Android Developer",
                "React Native Developer",
                "UI/UX Designer",
                "Graphic Designer",
                "Product Designer",
                "3D Modeler",
                "Content Creator",
                "Data Analyst",
                "DevOps Engineer",
                "communication",
                "teamwork",
                "adaptability",
                "task management",
                "time management",
                "leadership",
                "project management",
                "learning ability"
]

        data = []
        for user in User.objects.all():
            user_skills_qs = UserSkill.objects.filter(user=user)
            # 🔹 მომხმარებლის უნარების ვექტორი
            skill_vector = {
                s: user_skills_qs.filter(skill__name=s).first().points 
                if user_skills_qs.filter(skill__name=s).exists() else 0
                for s in all_skills
            }

            try:
                 target_job = user.profile.job.title
            except Exception:
                # თუ პროფილი ან სამუშაო არ არის, დეფოლტად
                target_job = random.choice(possible_jobs)

            skill_vector['role'] = target_job
            data.append(skill_vector)

        if not data:
            self.stdout.write(self.style.WARNING("⚠️ No user data found. Training skipped."))
            return

        # 🔹 DataFrame
        df = pd.DataFrame(data)
        X = df.drop("role", axis=1)
        y = df["role"]

        # 🔹 Train Decision Tree Classifier
        clf = DecisionTreeClassifier()
        clf.fit(X, y)

        # 🔹 Save the model
        model_path = os.path.join("app", "ml", "model.pkl")
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(clf, model_path)

        self.stdout.write(self.style.SUCCESS("✅ ML Model trained and saved dynamically!"))
