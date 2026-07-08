from core.resolver import Resolver


def print_course(course):

    print("-" * 80)

    # Format the list of historical codes into a readable string
    codes = course.get("course_codes", [])
    codes_str = ", ".join(codes) if codes else "N/A"

    print(f"Course Codes   : {codes_str}")

    print(f"Course ID      : {course.get('course_id', 'N/A')}")

    print(f"Title          : {course.get('title', 'N/A')}")

    print(f"Professor      : {course.get('professor', 'N/A')}")

    print(f"Institute      : {course.get('institute', 'N/A')}")

    print(f"Discipline     : {course.get('discipline', 'N/A')}")

    print(f"Score          : {course.get('score', 'N/A')}")

    print(f"Stats Status   : {course.get('stats_status', False)}")

    # Display high-level analytics if they exist
    if course.get("stats_status", False):
        print(f"Enrolled       : {course.get('total_enrolled', '0')}")
        print(f"Certified      : {course.get('total_certified', '0')}")

    print(f"URL            : {course.get('url', 'N/A')}")

    print()


def main():

    resolver = Resolver()

    print("=" * 80)
    print("NPTEL Course Search")
    print("=" * 80)

    while True:

        query = input("\nEnter Course Name, Code, or ID (or 'exit'): ").strip()

        if query.lower() == "exit":
            break

        if query == "":
            continue

        results = resolver.search(query, top_n=10)

        if not results:
            print("\nNo matching courses found.")
            continue

        print()

        print(f"Top {len(results)} Results")

        print("=" * 80)

        for i, course in enumerate(results, start=1):

            print(f"{i}.")

            print_course(course)


if __name__ == "__main__":

    main()