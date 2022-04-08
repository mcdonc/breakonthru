import argparse
import os
import random

def playrandom(directory, sink, volume):
    files = os.listdir(directory)
    fn = os.path.join(directory, random.choice(files))
    os.system(f"paplay -d {sink} --volume={volume} {fn}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--sink', help="Pulse sink to which to play a random wav file",
        required=True)
    parser.add_argument(
        '--dir', help="Directory full of wav files",
        required=True)
    parser.add_argument(
        '--volume', help="Choose a value between 0 (silent) and 65536 (100% volume)",
        type=int,
        default=16384)
    args = parser.parse_args()
    playrandom(args.dir, args.sink, args.volume)
