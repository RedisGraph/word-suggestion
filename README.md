# word-suggestion

This is a demo application for word completion/suggestion similar to auto-complete mobile keyboards
where given a previous word and a prefix the system will try to predict which word should follow.
<img src="/img/demo.gif"/>

## Running
Make sure [RedisGraph](http://redisgraph.io/) is accessible,

```
docker run --rm -p 6379:6379 redislabs/redisgraph:edge
```

### Load data
```python
python3 load.py
```

### Run suggestion server
```python
python3 complete.py
```

Tab to iterate through suggestions
Space to accept current suggestion

## Graph model
* Nodes represent words
* Edge connecting two words A and B with weight N indicates we've encountered N instances of the pair A B.

### Full-Text search over Redis by RedisLabs
<img src="/img/model.png"/>

## Personalization
Whenever a suggestion is accepted we reinforce to edge connecting the previous word and the suggestion by increasing its weight, in-case a word did not exist in the graph it is created.
