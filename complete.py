import sys
import getch
import redis
# from stemming.porter2 import stem
from enum import Enum
from redisgraph import Node, Edge, Graph

MIN_REQUIRED_SUGGESTIONS = 5

class TerminalColors(Enum):
	RED =    "\033[1;31m"
	BLUE =   "\033[1;34m"
	CYAN =   "\033[1;36m"
	GREEN =  "\033[0;32m"
	RESET =  "\033[0;0m"
	BOLD =     "\033[;1m"
	REVERSE =  "\033[;7m"

class Queries(Enum):
	suggest_word_long_prefix = "CALL db.idx.fulltext.queryNodes('word', $prefix) YIELD node as w RETURN w.value ORDER BY outdegree(w) DESC LIMIT " + str(MIN_REQUIRED_SUGGESTIONS)
	suggest_word_short_prefix = "MATCH (w:word) WHERE w.value starts with $prefix RETURN w.value ORDER BY outdegree(w) DESC LIMIT " + str(MIN_REQUIRED_SUGGESTIONS)
	suggest_word_short_no_prefix = "MATCH (w:word) RETURN w.value ORDER BY outdegree(w) DESC LIMIT " + str(MIN_REQUIRED_SUGGESTIONS)

	suggest_following_word_no_prefix = "MATCH (w:word {value: $given})-[e]->(z) RETURN z.value, e.v ORDER BY e.v DESC LIMIT " + str(MIN_REQUIRED_SUGGESTIONS)
	suggest_following_word_short_prefix = "MATCH (w:word {value: $given})-[e]->(z) WHERE z.value starts with $prefix RETURN z.value, e.v ORDER BY e.v DESC LIMIT " + str(MIN_REQUIRED_SUGGESTIONS)
	suggest_following_word_long_prefix = "CALL db.idx.fulltext.queryNodes('word', $prefix) YIELD node as z MATCH (w:word {value: $given})-[e]->(z) RETURN z.value, e.v ORDER BY e.v DESC LIMIT " + str(MIN_REQUIRED_SUGGESTIONS)

	introduce_word = "MERGE (:word {value:$W})"
	accept_suggestion = "MERGE (a:word {value:$W0}) MERGE (b:word {value:$W1}) MERGE(a)-[e:leads]->(b) ON MATCH SET e.v = e.v+1 ON CREATE SET e.v = 1"

class Keys(Enum):
	TAB = 0x09
	SPACE = 0x20
	NEW_LINE = 0x0A
	CARRIAGE_RETURN = 0X0D
	BACKSPACE = 0x7F

ERASE_LINE = '\x1b[2K'

r = redis.Redis(host='localhost', port=6379)
redis_graph = Graph('autocomplete', r)

line = ''
suggestions = []
accepted_words = []
current_prefix = ''
current_suggestion = ''
current_suggestion_idx = 0

def resetState():
	global line
	global suggestions
	global accepted_words
	global current_prefix
	global current_suggestion
	global current_suggestion_idx

	line = ''
	suggestions = []
	accepted_words = []
	current_prefix = ''
	current_suggestion = ''
	current_suggestion_idx = 0

def deleteChar():
	global current_prefix
	if len(current_prefix) > 0:
		current_prefix = current_prefix[:-1]

def terminal_erase_line():
	sys.stdout.write(chr(Keys.CARRIAGE_RETURN.value))
	sys.stdout.write(ERASE_LINE)

def getSuggestionsFollowingWord(word, prefix):
	suggestions = []
	has_prefix = len(prefix) > 0
	can_use_fulltext = len(prefix) > 1

	if can_use_fulltext:
		suggestions = redis_graph.query(Queries.suggest_following_word_long_prefix.value.replace('$prefix', "'" + prefix + '*\''), {'given': word}).result_set
	elif has_prefix:
		suggestions = redis_graph.query(Queries.suggest_following_word_short_prefix.value, {'prefix': prefix, 'given': word}).result_set
	else:
		suggestions = redis_graph.query(Queries.suggest_following_word_no_prefix.value, {'given': word}).result_set

	return suggestions

def getSuggestionsForPrefix(prefix):
	suggestions = []
	has_prefix = len(prefix) > 0
	can_use_fulltext = len(prefix) > 1

	if can_use_fulltext:
		suggestions = redis_graph.query(Queries.suggest_word_long_prefix.value.replace('$prefix', "'" + prefix + '*\'')).result_set
	elif has_prefix:
		suggestions = redis_graph.query(Queries.suggest_word_short_prefix.value, {'prefix': prefix}).result_set
	else:
		suggestions = redis_graph.query(Queries.suggest_word_short_no_prefix.value).result_set
	return suggestions

def getSuggestions():
	global suggestions
	global current_suggestion_idx

	prev_word = None
	current_suggestion_idx = 0

	if len(accepted_words) > 0:
		prev_word = accepted_words[-1]

	if prev_word:
		suggestions = getSuggestionsFollowingWord(prev_word, current_prefix)
		if len(suggestions) < MIN_REQUIRED_SUGGESTIONS:
			suggestions += getSuggestionsForPrefix(current_prefix)
	else:
		# No prev word.
		suggestions = getSuggestionsForPrefix(current_prefix)

def scrollSuggestion():
	global line
	global suggestions
	global current_suggestion
	global current_suggestion_idx

	current_suggestion = ''
	if len(suggestions) == 0:
		return ''

	# Alow user to consume its prefix.
	if current_suggestion_idx == len(suggestions):
		current_suggestion_idx += 1
		return ''

	# Round robin.
	if current_suggestion_idx > len(suggestions):
		current_suggestion_idx = 0

	# Get current suggestion, remove prefix.
	current_suggestion = suggestions[current_suggestion_idx][0]
	current_suggestion_idx += 1

	# 'b'
	current_suggestion = current_suggestion[2:-1]

def acceptSuggestion():
	global accepted_words
	global current_prefix
	global suggestions
	global current_suggestion
	global current_suggestion_idx

	accepted_word = current_prefix + current_suggestion[len(current_prefix):]

	# Make sure accepted word is in our graph.
	redis_graph.query(Queries.introduce_word.value, {'W': accepted_word})

	# Strength relation between prev word and used suggestion.
	if len(accepted_words) > 0:
		prev_word = accepted_words[-1]
		redis_graph.query(Queries.accept_suggestion.value, {'W0': prev_word, 'W1':accepted_word})

	# TODO: Decrease relation between prev word and unused suggestions.

	accepted_words.append(accepted_word)
	suggestions = []
	current_prefix = ''
	current_suggestion = ''
	current_suggestion_idx = 0

def newLine():
	sys.stdout.write(chr(Keys.NEW_LINE.value))
	sys.stdout.flush()
	resetState()

def updateConsole():
	line = ' '.join(accepted_words + [''])
	suggestion = current_suggestion[len(current_prefix):]

	# Return to start of line.
	terminal_erase_line()

	# Print what we've accumulated so far.
	sys.stdout.write(line)
	sys.stdout.write(current_prefix)
	sys.stdout.flush()

	# Print suggestion.
	sys.stdout.write(TerminalColors.RED.value)
	sys.stdout.write(suggestion)
	sys.stdout.write(TerminalColors.RESET.value)
	sys.stdout.flush()

def main():
	global current_prefix

	getSuggestions()
	scrollSuggestion()
	updateConsole()

	while True:
		char = getch.getch() # User input, but not displayed on the screen
		key = ord(char)
		if key == Keys.BACKSPACE.value:
			deleteChar()
			updateConsole()

		elif key == Keys.TAB.value:
			scrollSuggestion()
			updateConsole()
			continue

		elif key == Keys.SPACE.value:
			acceptSuggestion()

		elif key == Keys.NEW_LINE.value:
			acceptSuggestion()
			newLine()
		
		else:
			current_prefix += char

		getSuggestions()
		scrollSuggestion()
		updateConsole()

if __name__ == '__main__':
	main()
