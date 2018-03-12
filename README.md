# DEXBot

Trading Bot for the BitShares Decentralized Exchange (DEX).

## Build status

master:  
[![Build Status](https://travis-ci.org/Codaone/DEXBot.svg?branch=master)](https://travis-ci.org/Codaone/DEXBot)


**Warning**: This is highly experimental code! Use at your OWN risk!

## Installation

Python 3.4+ & pip are required. With make:

    $ git clone https://github.com/codaone/dexbot
    $ cd dexbot    
    $ make install    

or

    $ make install-user

Without make:

    $ git clone https://github.com/codaone/dexbot
    $ cd dexbot
    $ pip install -r requirements.txt
    $ python setup.py install

or

    $ pip install -r --user requirements.txt
    $ python setup.py install --user

## Configuration

Configuration happens in `config.yml`

## Requirements

Add your account's private key to the pybitshares wallet using `uptick`

    uptick addkey

## Execution

    dexbot run

# IMPORTANT NOTE

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
