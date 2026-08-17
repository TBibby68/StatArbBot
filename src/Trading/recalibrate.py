import pricesStarter
import starterForCloudInstanceOfBot

def main():
    print("booting up stat arb bot...")
    pricesStarter.main()
    starterForCloudInstanceOfBot.main()

if __name__ == "__main__":
    main()

# this file runs just the starters, which we need to do every 2 weeks to test for updated cointegration