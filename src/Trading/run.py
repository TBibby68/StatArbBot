import pricesStarter
import starterForCloudInstanceOfBot
import ibkrAPIEvents

def main():
    print("booting up stat arb bot...")
    pricesStarter.main()
    starterForCloudInstanceOfBot.main()
    ibkrAPIEvents.main()

if __name__ == "__main__":
    main()

# this file runs the starts and then the actual bot