# DEXBot

![GUI](https://i.imgur.com/rW8XKQ4.png)The Dashboard of the GUI version of DEXBot

![CLI](https://i.imgur.com/H1N96nI.png)The CLI version of DEXBot in configuration dialog

A Trading Bot provided with two very flexible Market Making strategies. Works on "vanilla" BitShares and all exchanges built upon it. Can be customized with additional strategies written in Python3.

DEXBot can be installed from source or by using the excecutable packages for Windows, OSX, and Linux. Packages include the GUI version, but installation from source provides also the CLI version, which can be used on headless servers and Raspberry Pi's.

The provided strategies can be used to bootstrap new markets, to increase liquidity of an asset, or to try to make profits.
The _Relative Orders_ strategy is the one most think of when speaking of _Market Making_. In most markets it requires tweaking and active monitoring, and is most suitable for sideways markets or _Arbitrage Enabling_ markets (between stable or otherwise equivalent assets). _Staggered Orders_ is a "set and forget" strategy, which thrives in uncertain conditions (before price discovery or otherwise volatile conditions). It requires a long time to realize profits, but is likely to do so if it isn't touched in the mean time. It requires little monitoring and no tweaking. New markets and assets should be bootstrapped with _Staggered Orders_ and later improved with _Relative Orders_.

**Make sure to read strategy documentation from the wiki.** [Here](https://link.medium.com/gXkfewn6XR) is a step-by-step guide to get started

## Does it make profit?
If you properly predict future market conditions, you can manage to make profit. All strategies rely on assumptions. The strategies that rely on less assumptions are less risky, and more risky strategies _can_ make more profit. During long declines the effect is decreased losses - not actual profits. So we can only say that it can make profit, without forgetting that it can also make losses. Good luck.

## Getting help
Join the [Telegram Chat for DEXBot](https://t.me/DEXBOTbts).

## Installing and running the software

See instructions in the [Wiki](https://github.com/Codaone/DEXBot/wiki) for [Linux](https://github.com/Codaone/DEXBot/wiki/Setup-Guide-for-Linux), [Windows](https://github.com/Codaone/DEXBot/wiki/Setup-Guide-for-Windows), [OSX](https://github.com/Codaone/DEXBot/wiki/Setup-Guide-for-Mac-OS-X). [Raspberry Pi](https://github.com/Codaone/DEXBot/wiki/Setup-guide-for-Raspberry-Pi). Other users can try downloading the package or following the Linux guide.

## Build status

master:  
[![Build Status](https://travis-ci.org/Codaone/DEXBot.svg?branch=master)](https://travis-ci.org/Codaone/DEXBot)


**Warning**: This is highly experimental code! Use at your OWN risk!



## Contributing

Install the software, use it and report any problems by creating a ticket.

# IMPORTANT NOTE

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
