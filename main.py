import sys, json, collections


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "bot"
    if cmd == "bot":          # production: daily schedule + Telegram approvals
        import bot
        bot.start()
    elif cmd == "auth":       # one-time YouTube login
        import youtube
        youtube.authorize()
    elif cmd == "sources":    # check what each source is returning
        import collect
        items = collect.collect()
        print(collections.Counter(i["source"].split(" r/")[0] for i in items))
        print("Trends:", collect.trending_terms()[:15])
    elif cmd == "dry":        # Week-1 testing: print scripts only, no voice/images/video/upload
        import pipeline
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
        for story in pipeline.plan()[:n]:
            r = pipeline.script_only(story)
            if r:
                print(f"\n===== [{story['lane']}] {story['topic_en']} =====")
                print(json.dumps({"script": r["script"], "check": r["check"]}, ensure_ascii=False, indent=2))
    else:
        print("usage: python main.py [bot|auth|sources|dry [N]]")


if __name__ == "__main__":
    main()
