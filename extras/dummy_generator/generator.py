# -*- coding: utf-8 -*-

# This file is part of wger Workout Manager.
#
# wger Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wger Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License

# Standard Library
import argparse
import csv
import datetime
import os
import random
import sys
import uuid

# Django
import django
from django.db import IntegrityError
from django.utils import timezone
from django.utils.text import slugify

sys.path.insert(0, os.path.join('..', '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

# Django
# Must happen after calling django.setup()
from django.contrib.auth.models import User

# wger
from wger.core.models import (
    DaysOfWeek,
    Language,
)
from wger.exercises.models import Exercise
from wger.gym.models import (
    Gym,
    GymUserConfig,
)
from wger.manager.models import (
    Day,
    Schedule,
    ScheduleStep,
    Set,
    Setting,
    Workout,
    WorkoutLog,
    WorkoutSession,
)
from wger.measurements.models import (
    Category,
    Measurement,
)
from wger.nutrition.models import (
    Ingredient,
    LogItem,
    Meal,
    MealItem,
    NutritionPlan,
)
from wger.weight.models import WeightEntry

parser = argparse.ArgumentParser(description='Data generator. Please consult the documentation')
subparsers = parser.add_subparsers(help='The kind of entries you want to generate')

# User options
user_parser = subparsers.add_parser('users', help='Create users')
user_parser.add_argument('number_users', action='store', help='Number of users to create', type=int)
user_parser.add_argument(
    '--add-to-gym',
    action='store',
    default='auto',
    help='Gym to assign the users to. Allowed values: auto, none, <gym_id>. '
         'Default: auto'
)
user_parser.add_argument(
    '--country',
    action='store',
    default='germany',
    help='What country the generated users should belong to. Default: Germany',
    choices=['germany', 'ukraine', 'spain', 'usa']
)

# Workout options
workouts_parser = subparsers.add_parser('workouts', help='Create workouts')
workouts_parser.add_argument(
    'number_workouts',
    action='store',
    help='Number of workouts to create *per user*',
    type=int,
)
workouts_parser.add_argument(
    '--add-to-user',
    action='store',
    help='Add to the specified user-ID, not all existing users',
)

# Gym options
gym_parser = subparsers.add_parser('gyms', help='Create gyms')
gym_parser.add_argument(
    'number_gyms',
    action='store',
    help='Number of gyms to create',
    type=int,
)
# Log options
logs_parser = subparsers.add_parser('logs', help='Create logs')
logs_parser.add_argument(
    'number_logs',
    action='store',
    help='Number of logs to create per user and workout',
    type=int,
)

# Session options
session_parser = subparsers.add_parser('sessions', help='Create sessions')
session_parser.add_argument(
    'impression_sessions',
    action='store',
    help='Impression for the sessions, default: random',
    default='random',
    choices=['random', 'good', 'neutral', 'bad']
)

# Weight options
weight_parser = subparsers.add_parser('weight', help='Create weight entries')
weight_parser.add_argument(
    'number_weight',
    action='store',
    help='Number of weight entries to create per user',
    type=int,
)
weight_parser.add_argument(
    '--add-to-user',
    action='store',
    help='Add to the specified user-ID, not all existing users',
)
weight_parser.add_argument(
    '--base-weight',
    action='store',
    help='Default weight for the entry generation, default = 80',
    type=int,
    default=80,
)

# Measurement options
measurement_parser = subparsers.add_parser('measurement', help='Create measurement entries')
measurement_parser.add_argument(
    'number_measurement',
    action='store',
    help='Number of measurement entries to create per user',
    type=int
)
measurement_parser.add_argument(
    '--add-to-user',
    action='store',
    help='Add to the specified user-ID, not all existing users',
)

# Nutrition options
nutrition_parser = subparsers.add_parser(
    'nutrition',
    help='Creates a meal plan',
)
nutrition_parser.add_argument(
    'number_nutrition_plans',
    action='store',
    help='Number of meal plans to create',
    type=int,
)
nutrition_parser.add_argument(
    '--add-to-user',
    action='store',
    help='Add to the specified user-ID, not all existing users',
)

# Nutrition diary options
nutrition_parser = subparsers.add_parser('nutrition-diary', help='Creates a meal plan')
nutrition_parser.add_argument(
    'number_nutrition_logs',
    action='store',
    help='Number of nutrition diary logs to create',
    type=int
)
nutrition_parser.add_argument(
    '--number-diary-dates',
    action='store',
    help='Number of dates in which to create logs (default: 30)',
    default=30,
    type=int
)
nutrition_parser.add_argument(
    '--add-to-user',
    action='store',
    help='Add to the specified user-ID, not all existing users',
)

args = parser.parse_args()
# print(args)

#
# User generator
#
if hasattr(args, 'number_users'):
    print("** Generating {0} users".format(args.number_users))

    try:
        gym_list = [int(args.add_to_gym)]
    except ValueError:
        if args.add_to_gym == 'none':
            gym_list = []
        else:
            gym_list = [i['id'] for i in Gym.objects.all().values()]

    first_names = []
    last_names = []

    with open(os.path.join('csv', 'first_names_{0}.csv'.format(args.country))) as name_file:
        name_reader = csv.reader(name_file)
        for row in name_reader:
            first_names.append(row)

    with open(os.path.join('csv', 'last_names_{0}.csv'.format(args.country))) as name_file:
        name_reader = csv.reader(name_file)
        for row in name_reader:
            last_names.append(row[0])

    for i in range(1, args.number_users):
        uid = uuid.uuid4()
        name_data = random.choice(first_names)
        name = name_data[0]
        gender = name_data[1]
        surname = random.choice(last_names)

        username = slugify('{0}, {1} {2}'.format(name, surname[0], str(uid).split('-')[1]))
        email = '{0}@example.com'.format(username)
        password = username

        try:
            user = User.objects.create_user(username, email, password)
            user.first_name = name
            user.last_name = surname
            user.save()

        # Even with the uuid part, usernames are not guaranteed to be unique,
        # in this case, just ignore and continue
        except IntegrityError as e:
            continue

        if gym_list:
            gym_id = random.choice(gym_list)
            user.userprofile.gym_id = gym_id
            user.userprofile.gender = '1' if gender == 'm' else 2
            user.userprofile.age = random.randint(18, 45)
            user.userprofile.save()

            config = GymUserConfig()
            config.gym_id = gym_id
            config.user = user
            config.save()

        print('   - {0}, {1}'.format(name, surname))

#
# Gym generator
#
if hasattr(args, 'number_gyms'):
    print("** Generating {0} gyms".format(args.number_gyms))

    gym_list = []

    names_part1 = []
    names_part2 = []

    with open(os.path.join('csv', 'gym_names.csv')) as name_file:
        name_reader = csv.reader(name_file)
        for row in name_reader:
            if row[0]:
                names_part1.append(row[0])
            if row[1]:
                names_part2.append(row[1])

    for i in range(1, args.number_gyms):
        found = False
        while not found:
            part1 = random.choice(names_part1)
            part2 = random.choice(names_part2)

            # We don't want names like "Iron Iron"
            if part1 != part2:
                found = True

        name = "{0} {1}".format(part1, part2)
        gym = Gym()
        gym.name = name
        gym_list.append(gym)

        print('   - {0}'.format(gym.name))

    # Bulk-create all the gyms
    Gym.objects.bulk_create(gym_list)

#
# Workout generator
#
if hasattr(args, 'number_workouts'):
    print("** Generating {0} workouts per user".format(args.number_workouts))

    if args.add_to_user:
        userlist = [User.objects.get(pk=args.add_to_user)]
    else:
        userlist = User.objects.all()

    for user in userlist:
        print('   - generating for {0}'.format(user.username))

        # Workouts
        for i in range(1, args.number_workouts):

            uid = str(uuid.uuid4()).split('-')
            start_date = datetime.date.today() - datetime.timedelta(days=random.randint(0, 100))
            workout = Workout(
                user=user,
                name='Dummy workout - {0}'.format(uid[1]),
                creation_date=start_date,
            )
            workout.save()

            # Select a random number of workout days
            nr_of_days = random.randint(1, 5)
            day_list = [i for i in range(1, 8)]
            random.shuffle(day_list)

            # Load all exercises to a list
            exercise_list = [i for i in Exercise.objects.filter(language_id=2)]

            for day in day_list[0:nr_of_days]:
                uid = str(uuid.uuid4()).split('-')
                weekday = DaysOfWeek.objects.get(pk=day)

                day = Day(training=workout, description='Dummy day - {0}'.format(uid[0]))
                day.save()
                day.day.add(weekday)

                # Select a random number of exercises
                nr_of_exercises = random.randint(3, 10)
                random.shuffle(exercise_list)
                day_exercises = exercise_list[0:nr_of_exercises]
                order = 1
                for exercise in day_exercises:
                    reps = random.choice([1, 3, 5, 8, 10, 12, 15])
                    sets = random.randint(2, 4)

                    day_set = Set(exerciseday=day, sets=sets, order=order)
                    day_set.save()

                    setting = Setting(
                        set=day_set,
                        exercise_base=exercise.exercise_base,
                        reps=reps,
                        order=order,
                    )
                    setting.save()
                    order += 1

        # Schedules
        nr_of_schedules = random.randint(1, 5)
        user_workouts = [i for i in Workout.objects.filter(user=user)]
        for i in range(0, nr_of_schedules):
            uid = str(uuid.uuid4()).split('-')
            start_date = datetime.date.today() - datetime.timedelta(days=random.randint(0, 30))

            random.shuffle(user_workouts)

            schedule = Schedule()
            schedule.user = user
            schedule.name = 'Dummy schedule - {0}'.format(uid[1])
            schedule.start_date = start_date
            schedule.is_active = True
            schedule.is_loop = True
            schedule.save()

            nr_of_steps = random.randint(1, len(user_workouts))
            order = 1
            for j in range(1, nr_of_steps):
                step = ScheduleStep()
                step.schedule = schedule
                step.workout = workout
                step.duration = random.randint(1, 4)
                step.order = order
                step.save()

                order += 1

#
# Log generator
#
if hasattr(args, 'number_logs'):
    print("** Generating {0} logs".format(args.number_logs))

    for user in User.objects.all():
        weight_log = []
        print('   - generating for {0}'.format(user.username))

        # Create a log for each workout day, set, setting, reps, weight, date
        for workout in Workout.objects.filter(user=user):
            for day in workout.day_set.all():
                for set in day.set_set.all():
                    for setting in set.setting_set.all():
                        for reps in (8, 10, 12):
                            for i in range(1, args.number_logs):
                                date = datetime.date.today() - datetime.timedelta(weeks=i)
                                log = WorkoutLog(
                                    user=user,
                                    exercise_base=setting.exercise_base,
                                    workout=workout,
                                    reps=reps,
                                    weight=50 - reps + random.randint(1, 10),
                                    date=date
                                )
                                weight_log.append(log)

        # Bulk-create the logs
        WorkoutLog.objects.bulk_create(weight_log)

#
# Session generator
#
if hasattr(args, 'impression_sessions'):
    print("** Generating workout sessions")

    for user in User.objects.all():
        session_list = []
        print('   - generating for {0}'.format(user.username))

        for date in WorkoutLog.objects.filter(user=user).dates('date', 'day'):

            # Only process for dates for which there isn't already a session
            if not WorkoutSession.objects.filter(user=user, date=date).exists():

                workout = WorkoutLog.objects.filter(user=user, date=date).first().workout
                start = datetime.time(hour=random.randint(8, 20), minute=random.randint(0, 59))
                end = datetime.datetime.combine(datetime.date.today(), start) \
                      + datetime.timedelta(minutes=random.randint(40, 120))
                end = datetime.time(hour=end.hour, minute=end.minute)

                session = WorkoutSession()
                session.date = date
                session.user = user
                session.time_start = start
                session.time_end = end
                session.workout = workout

                if args.impression_sessions == 'good':
                    session.impression = WorkoutSession.IMPRESSION_GOOD
                elif args.impression_sessions == 'neutral':
                    session.impression = WorkoutSession.IMPRESSION_NEUTRAL
                elif args.impression_sessions == 'bad':
                    session.impression = WorkoutSession.IMPRESSION_BAD
                else:
                    session.impression = random.choice(
                        [
                            WorkoutSession.IMPRESSION_GOOD,
                            WorkoutSession.IMPRESSION_NEUTRAL,
                            WorkoutSession.IMPRESSION_BAD,
                        ]
                    )

                session_list.append(session)

        # Bulk-create the sessions
        WorkoutSession.objects.bulk_create(session_list)

#
# Weight entry generator
#
if hasattr(args, 'number_weight'):
    print("** Generating {0} weight entries per user".format(args.number_weight))

    if args.add_to_user:
        userlist = [User.objects.get(pk=args.add_to_user)]
    else:
        userlist = User.objects.all()

    for user in userlist:
        new_entries = []
        print('   - generating for {0}'.format(user.username))

        existing_entries = [i.date for i in WeightEntry.objects.filter(user=user)]

        # Weight entries
        for i in range(1, args.number_weight):

            creation_date = datetime.date.today() - datetime.timedelta(days=i)
            if creation_date not in existing_entries:
                entry = WeightEntry(
                    user=user,
                    weight=args.base_weight + 0.5 * i + random.randint(1, 3),
                    date=creation_date
                )
                new_entries.append(entry)

        # Bulk-create the weight entries
        WeightEntry.objects.bulk_create(new_entries)

#
# Measurement entry generator
#
if hasattr(args, 'number_measurement'):
    print("** Generating {0} measurement entries per user".format(args.number_measurement))

    # Load units
    units = []
    with open(os.path.join('csv', 'measurement_categories.csv')) as category_file:
        category_reader = csv.reader(category_file)
        for row in category_reader:
            units.append({'name': row[0], 'unit': row[1]})

    # User list
    if args.add_to_user:
        userlist = [User.objects.get(pk=args.add_to_user)]
    else:
        userlist = User.objects.all()

    new_entries = []
    for user in userlist:
        BASE_VALUE = random.randint(80, 100)
        print('   - generating measurements for {0}'.format(user.username))
        existing_entries = [i.date for i in Measurement.objects.filter(category__user=user)]

        for measurement_cat in random.choices(units, k=4):
            print(measurement_cat)

            cat = Category(
                name=measurement_cat['name'],
                unit=measurement_cat['unit'],
                user=user,
            )
            cat.save()

            for i in range(1, args.number_measurement):
                creation_date = datetime.date.today() - datetime.timedelta(days=i)

                if creation_date not in existing_entries:
                    measurement = Measurement(
                        category=cat,
                        value=BASE_VALUE + 0.5 * i + random.randint(-20, 10),
                        date=creation_date,
                    )
                    new_entries.append(measurement)

    # Bulk-create the entries
    Measurement.objects.bulk_create(new_entries)

#
# Nutrition Generator
#
if hasattr(args, 'number_nutrition_plans'):
    print("** Generating {0} nutrition plan(s) per user".format(args.number_nutrition_plans))

    if args.add_to_user:
        userlist = [User.objects.get(pk=args.add_to_user)]
    else:
        userlist = User.objects.all()

    # Load all ingredients to a list
    ingredient_list = [i for i in Ingredient.objects.order_by('?').all()[:100]]

    # Total meals per plan
    TOTAL_MEALS = 4

    for user in userlist:
        print('   - generating for {0}'.format(user.username))

        # Add nutrition plan
        for i in range(0, args.number_nutrition_plans):
            uid = str(uuid.uuid4()).split('-')
            start_date = datetime.date.today() - datetime.timedelta(days=random.randint(0, 100))
            nutrition_plan = NutritionPlan(
                language=Language.objects.all()[1],
                description='Dummy nutrition plan - {0}'.format(uid[1]),
                creation_date=start_date,
            )
            nutrition_plan.user = user

            nutrition_plan.save()

            # Add meals to plan
            order = 1
            for j in range(0, TOTAL_MEALS):
                meal = Meal(
                    plan=nutrition_plan,
                    order=order,
                    time=datetime.time(hour=random.randint(0, 23), minute=random.randint(0, 59))
                )
                meal.save()
                for k in range(0, random.randint(1, 5)):
                    ingredient = random.choice(ingredient_list)
                    meal_item = MealItem(
                        meal=meal,
                        ingredient=ingredient,
                        weight_unit=None,
                        order=order,
                        amount=random.randint(10, 250)
                    )
                    meal_item.save()
                order = order + 1

#
# Nutrition diary Generator
#
if hasattr(args, 'number_nutrition_logs'):
    print("** Generating {0} nutrition diary entries per user".format(args.number_nutrition_logs))

    if args.add_to_user:
        userlist = [User.objects.get(pk=args.add_to_user)]
    else:
        userlist = User.objects.all()

    # Load all ingredients to a list
    ingredient_list = [i for i in Ingredient.objects.order_by('?').all()[:100]]

    for user in userlist:
        plan_list = NutritionPlan.objects.order_by('?').filter(user=user)
        print('   - generating for {0}'.format(user.username))

        # Add diary entries
        for plan in NutritionPlan.objects.filter(user=user):
            for i in range(0, args.number_diary_dates):
                date = timezone.now() - datetime.timedelta(
                    days=random.randint(0, 100),
                    hours=random.randint(0, 12),
                    minutes=random.randint(0, 59)
                )
                for j in range(0, args.number_nutrition_logs):
                    ingredient = random.choice(ingredient_list)
                    log = LogItem(
                        plan=plan,
                        datetime=date,
                        ingredient=ingredient,
                        weight_unit=None,
                        amount=random.randint(10, 300)
                    )
                    log.save()
