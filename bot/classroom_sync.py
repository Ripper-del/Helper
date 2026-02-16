from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from datetime import datetime
import os
from database import get_db, Deadline, Coursework

os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'


def get_classroom_service(refresh_token: str):
    credentials = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=[
            'https://www.googleapis.com/auth/classroom.courses.readonly',
            'https://www.googleapis.com/auth/classroom.course-work.readonly'
        ]
    )
    return build('classroom', 'v1', credentials=credentials)


def fetch_all_deadlines(refresh_token: str):
    try:
        service = get_classroom_service(refresh_token)
        courses_response = service.courses().list(
            courseStates=['ACTIVE'],
            pageSize=100
        ).execute()

        courses = courses_response.get('courses', [])
        all_deadlines = []
        all_coursework_no_deadline = []

        print(f"🔍 Знайдено курсів: {len(courses)}")

        for course in courses:
            course_id = course['id']
            course_name = course['name']

            try:
                coursework_response = service.courses().courseWork().list(
                    courseId=course_id,
                    pageSize=100
                ).execute()

                coursework_list = coursework_response.get('courseWork', [])

                if len(coursework_list) > 0:
                    print(f"📘 Курс '{course_name}': {len(coursework_list)} завдань.")

                for work in coursework_list:
                    work_title = work.get('title', 'Без назви')
                    link = work.get('alternateLink', '')
                    external_id = f"{course_id}_{work['id']}"
                    
                    # Проверяем наличие dueDate
                    if 'dueDate' not in work:
                        print(f"  ⚠️ Пропущено '{work_title}' - немає dueDate")
                        
                        # Сохраняем как coursework без дедлайна
                        coursework_data = {
                            'course_name': course_name,
                            'title': work_title,
                            'link': link,
                            'external_id': external_id
                        }
                        all_coursework_no_deadline.append(coursework_data)
                        continue

                    try:
                        due_date_dict = work.get('dueDate')
                        due_time_dict = work.get('dueTime', {})

                        due_date = datetime(
                            due_date_dict['year'],
                            due_date_dict['month'],
                            due_date_dict['day'],
                            due_time_dict.get('hours', 23),
                            due_time_dict.get('minutes', 59)
                        )

                        deadline_data = {
                            'course_name': course_name,
                            'title': work['title'],
                            'due_date': due_date,
                            'link': link,
                            'external_id': external_id
                        }

                        all_deadlines.append(deadline_data)
                        print(f"  ✅ Додано дедлайн '{work_title}' - {due_date.strftime('%d.%m.%Y %H:%M')}")
                    
                    except KeyError as e:
                        print(f"  ❌ Помилка парсингу дедлайну '{work_title}': відсутнє поле {e}")
                    except Exception as e:
                        print(f"  ❌ Помилка обробки '{work_title}': {e}")

            except Exception as e:
                print(f"❌ Ошибка при получении заданий курса {course_name}: {e}")
                import traceback
                traceback.print_exc()
                continue

        print(f"✅ Всього знайдено {len(all_deadlines)} дедлайнів та {len(all_coursework_no_deadline)} завдань без дедлайнів")
        return all_deadlines, all_coursework_no_deadline

    except RefreshError:
        print(f"❌ Token expired or revoked for fetch_all_deadlines")
        raise
    except Exception as e:
        print(f"❌ Ошибка при получении данных из Classroom: {e}")
        import traceback
        traceback.print_exc()
        return [], []


def sync_user_deadlines(user_id: int, telegram_id: int, google_token: str):
    """Синхронизация дедлайнов пользователя"""
    print(f"🔄 Синхронизация для user {telegram_id}...")

    deadlines_data, coursework_no_deadline_data = fetch_all_deadlines(google_token)
    
    # Получаем все курсы из Google Classroom
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        
        credentials = Credentials(
            None,
            refresh_token=google_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=[
                'https://www.googleapis.com/auth/classroom.courses.readonly',
                'https://www.googleapis.com/auth/classroom.course-work.readonly'
            ]
        )
        service = build('classroom', 'v1', credentials=credentials)
        courses_response = service.courses().list(
            courseStates=['ACTIVE'],
            pageSize=100
        ).execute()
        all_courses = [course['name'] for course in courses_response.get('courses', [])]
    except RefreshError:
        print(f"❌ Token expired or revoked for courses list")
        raise
    except:
        all_courses = []

    if not deadlines_data and not coursework_no_deadline_data:
        print(f"⚠️ Нет дедлайнов для user {telegram_id}")
        return 0, 0, all_courses

    db = get_db()
    added_count = 0
    updated_count = 0
    coursework_added = 0

    # Сохраняем дедлайны
    for dl_data in deadlines_data:
        existing = db.query(Deadline).filter(
            Deadline.external_id == dl_data['external_id']
        ).first()

        if existing:
            existing.due_date = dl_data['due_date']
            existing.title = dl_data['title']
            existing.link = dl_data['link']
            existing.notified = False
            updated_count += 1
        else:
            new_deadline = Deadline(
                user_id=user_id,
                course_name=dl_data['course_name'],
                title=dl_data['title'],
                due_date=dl_data['due_date'],
                link=dl_data['link'],
                external_id=dl_data['external_id'],
                notified=False
            )
            db.add(new_deadline)
            added_count += 1

    # Удаляем старые coursework без дедлайнов для этого пользователя
    db.query(Coursework).filter(Coursework.user_id == user_id).delete()

    # Сохраняем coursework без дедлайнов
    for cw_data in coursework_no_deadline_data:
        new_coursework = Coursework(
            user_id=user_id,
            course_name=cw_data['course_name'],
            title=cw_data['title'],
            link=cw_data['link'],
            external_id=cw_data['external_id']
        )
        db.add(new_coursework)
        coursework_added += 1

    db.commit()
    db.close()

    print(f"✅ User {telegram_id}: додано {added_count}, оновлено {updated_count}, завдань без дедлайнів: {coursework_added}")
    
    return added_count, updated_count, all_courses
