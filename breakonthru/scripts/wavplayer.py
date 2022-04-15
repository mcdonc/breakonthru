import argparse
import os
import random

def playrandom(directory, device):
    files = os.listdir(directory)
    fn = os.path.join(directory, random.choice(files))
    print(f"chose {fn}")
    os.system(f"aplay -D {device} {fn}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--device', help="Dev through which to play a random wav file (default hw:1,0)",
        default="hw:1,0")
    parser.add_argument(
        '--dir', help="Directory full of wav files",
        required=True)
    args = parser.parse_args()
    playrandom(args.dir, args.device)
