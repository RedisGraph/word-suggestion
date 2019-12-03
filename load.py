import redis
import operator
import progressbar
from stemming.porter2 import stem

from redisgraph import Node, Edge, Graph

REMOVE_CHARS = [',', '.', ':', '\'', '"', '/', '\n', '\t', '-', ';', '(', ')', '[', ']', '{', '}', '!', '@', '#', '$', '%', '^', '&', '*', '?']

r = redis.Redis(host='localhost', port=6379)
redis_graph = Graph('autocomplete', r)

# Load data.
r.flushall()

# Create Indecies:
redis_graph.query("CREATE INDEX ON :word(value)")
redis_graph.call_procedure("db.idx.fulltext.createNodeIndex", 'word', 'value')

# Populate graph.
with open("./data/words_alpha.txt") as file:
	content = file.read()
	words = content.split()
	words = [w.lower() for w in words if len(w) > 1]
	unique_words = set(words)

	max_node_count = len(unique_words)
	node_count = 0
	with progressbar.ProgressBar(max_value=max_node_count) as bar:
		for word in unique_words:
			n = Node(label='word', properties={'value': word})
			redis_graph.add_node(n)
			node_count += 1
			bar.update(node_count)
			if (node_count % 100) == 0:
				redis_graph.flush()

	# Flush left-overs.
	redis_graph.flush()

with open("./data/TwitterConvCorpus.txt") as file:
	content = file.read()
	for c in REMOVE_CHARS:
		content = content.replace(c, ' ')

	words = content.split()
	words = [w.lower() for w in words if len(w) > 1]

	max_edge_count = len(words) - 1
	with progressbar.ProgressBar(max_value=max_edge_count) as bar:
		for i in range(len(words) - 1):
			w0 = words[i]
			w1 = words[i+1]
			redis_graph.query("MATCH (a:word {value:$w0}), (b:word {value: $w1}) MERGE (a)-[e:leads]->(b) ON MATCH SET e.v = e.v+1 ON CREATE SET e.v = 1", {"w0": w0, "w1": w1})
			bar.update(i)
