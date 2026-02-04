from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import datetime
import os

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
                    
                    # Проверяем наличие dueDate
                    if 'dueDate' not in work:
                        print(f"  ⚠️ Пропущено '{work_title}' - немає dueDate")
                        print(f"     Доступні поля: {list(work.keys())}")
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

                        link = work.get('alternateLink', '')

                        deadline_data = {
                            'course_name': course_name,
                            'title': work['title'],
                            'due_date': due_date,
                            'link': link,
                            'external_id': f"{course_id}_{work['id']}"
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

        print(f"✅ Всього знайдено {len(all_deadlines)} дедлайнів")
        return all_deadlines

    except Exception as e:
        print(f"❌ Ошибка при получении данных из Classroom: {e}")
        import traceback
        traceback.print_exc()
        return []
