import argparse
import os
import random

def playrandom(directory, sink):
    files = os.listdir(directory)
    fn = os.path.join(directory, random.choice(files))
    os.system(f"paplay -d {sink} {fn}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--sink', help="Pulse sink to which to play a random wav file",
        required=True)
    parser.add_argument(
        '--dir', help="Directory full of wav files",
        required=True)
    args = parser.parse_args()
    playrandom(args.dir, args.sink)
