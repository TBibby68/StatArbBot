import StatArbBot.Trading.pricesStarter
import StatArbBot.Trading.starterForCloudInstanceOfBot
import StatArbBot.Trading.paperStream

def main():
    print("Running file1...")
    StatArbBot.Trading.pricesStarter.main()
    StatArbBot.Trading.starterForCloudInstanceOfBot.main()
    StatArbBot.Trading.paperStream.main()

if __name__ == "__main__":
    main()