# -*- coding: utf-8 -*-

'''
fasttextでベクトルにして学習するモデル
embeddingレイヤーでfasttextのベクトルを利用
gensimライブラリは使わない
多クラス分類みたいな感じで各単語の確率分布を出力するモデル

python    : 2.7.12
keras     : 2.0.4
gensim    : 3.0.1
tensorflow: 1.1.0

プログラム全体の構成
    ・グローバル変数一覧
    ・関数群
    ・いわゆるmain部みたいなの

プログラム全体の流れ
    0.いろいろ前準備
    1.学習データの前処理
    2.fasttextのロードと辞書の作成
    3.モデルの定義
    4.モデルの学習
    5.val_loss最小モデルのロード
    6.テストの実行
    7.結果まとめの出力

'''

from __future__ import print_function
from keras.models import Sequential, Model
from keras.models import model_from_json
from keras.layers import Dense, Activation, Input, Embedding
from keras.layers import LSTM
from keras.layers import add
from keras.optimizers import RMSprop
from keras.utils.data_utils import get_file
from keras.utils.vis_utils import plot_model
import keras
import numpy as np
import re
import random
import sys
import datetime
import os
import os.path
import matplotlib
matplotlib.use('Agg')    #これをpyplotより先に書くことでサーバでも動くようにしている
import matplotlib.pyplot as plt
import subprocess

#----- グローバル変数一覧 -----
my_epoch=2
vec_size=100
maxlen_words = 10
KeyError_set=set()
today_str=''
tmp_vec_dict=dict()


#TODO 最後にタブをスペースに置換



#----- 関数群 -----



#時間表示
def print_time(str1):
    today=datetime.datetime.today()
    print(str1)
    print(today)
    return today


#listの各要素を単語で連結してstring型で返す
def list_to_sent(list_line, start, end):
    sent=' '.join(list_line[start:end])
    return sent


#学習データへの前処理を行う
#小文字化，アルファベット以外の文字の削除，1万単語ごとに分割
def preprocess(train_path):
    max_len=50000
    new_path=train_path[:-4]+'_preprpcessed'+str(max_len)+'.txt'
    if os.path.exists(new_path)==False:
        
        print('Preprpcessing training data...')
        text=''
        text_len=0
        i=0
        with open(train_path) as f_in:
            with open(new_path, 'w') as f_out:
                for line in f_in:
                    i+=1
                    #この前処理はtext8とかの前処理と同じ
                    line=line.lower()
                    line=line.replace('0', ' zero ')
                    line=line.replace('1', ' one ')
                    line=line.replace('2', ' two ')
                    line=line.replace('3', ' three ')
                    line=line.replace('4', ' four ')
                    line=line.replace('5', ' five ')
                    line=line.replace('6', ' six ')
                    line=line.replace('7', ' seven ')
                    line=line.replace('8', ' eight ')
                    line=line.replace('9', ' nine ')
                    line = re.sub(r'[^a-z]', ' ', line)
                    line = re.sub(r'[ ]+', ' ', line)
                    line_list=line.split(' ')
                    line_len=len(line_list)
                    #max_len以下の時は連結して次へ
                    if(text_len+line_len <= max_len):
                        if(text_len==0):
                            text=line
                        else:
                            text=text+' '+line
                        text_len=text_len+line_len
                    #max_lenより長いときはmax_len単語ごとに区切ってファイルへ書き込み
                    else:
                        while (line_len>max_len):
                            if(text_len==0):
                                text=list_to_sent(line_list,0,max_len)
                            else:
                                text=text+' '+list_to_sent(line_list,0,max_len-text_len)
                            f_out.write(text+'\n')
                            text=''
                            text_len=0
                            #残りの更新
                            line_list=line_list[max_len-text_len+1:]
                            line_len=len(line_list)
                        #while 終わり（1行の末尾の処理）
                        #余りは次の行と連結
                        text=list_to_sent(line_list,0,line_len)
                        text_len=line_len
                #for終わり（ファイルの最後の行の処理）
                if text_len!=0:
                    f_out.write(text+'\n')
                print('total '+str(i)+' line\n')
                print_time('preprpcess end')
    
    return new_path


#fasttextのベクトルファイルから単語辞書とベクトル辞書の作成
def vec_to_dict(vec_path):
    print('Loading fasttext vec ...')
    s=set()
    word_indices=dict()
    indices_word=dict()
    vec_dict=dict()
    i=0
    text=''
    with open(vec_path,'r') as f:
        for line in f:
            if i!=0:
                #先頭行には単語数と次元数が書かれているので無視
                line=line.replace('\n', '').replace('\r','')
                if line[-1]==' ':
                    line=line[:-1]
                tmp_list=line.split(' ')
                word=tmp_list[0]
                str_list=tmp_list[1:]
                #辞書の作成
                #0番目はパディング用の数字なので使わないことに注意
                word_indices[word]=i
                indices_word[i]=word
                vec_dict[word]=np.array(str_list, dtype=np.float32)
            i+=1

    word_indices['#OTHER']=i
    indices_word[i]='#OTHER'
    len_words=i
    return len_words, word_indices, indices_word, vec_dict


#fasttextのベクトルを得る
#未知語の場合にはfasttextのモデル呼び出して実行
#未知語は集合に格納し，あとでファイル出力
def get_ft_vec(word, vec_dict, ft_path, bin_path):
    if word in vec_dict:
        return vec_dict[word]
    elif word in tmp_vec_dict:
        return tmp_vec_dict[word]
    else:
        KeyError_set.add(word)    #要素を追加
        cmd='echo "'+word+'" | '+ft_path+' print-word-vectors '+bin_path
        ret  =  subprocess.check_output(cmd, shell=True)

        line=ret.replace('\n', '').replace('\r','')
        if line[0]==' ':
            line=line[1:]
        if line[-1]==' ':
            line=line[:-1]
        tmp_list=line.split(' ')
        word=tmp_list[0]
        vec=tmp_list[1:]
        vec_array=np.array(vec,dtype=np.float32)
        tmp_vec_dict[word]=vec_array

        return vec_array


# モデルの構築
def build_model(len_words, embedding_matrix):
    f_input=Input(shape=(maxlen_words,))
    f_emb=Embedding(output_dim=vec_size, input_dim=len_words+1, input_length=maxlen_words, mask_zero=True, weights=[embedding_matrix], trainable=False)(f_input)

    f_layer=LSTM(128)(f_emb)

    r_input=Input(shape=(maxlen_words,))
    r_emb=Embedding(output_dim=vec_size, input_dim=len_words+1, input_length=maxlen_words, mask_zero=True, weights=[embedding_matrix], trainable=False)(r_input)
    r_layer=LSTM(128)(r_emb)

    merged_layer=add([f_layer, r_layer])

    out_layer=Dense(len_words+1,activation='softmax')(merged_layer)

    model=Model([f_input, r_input], out_layer)

    optimizer = RMSprop()
    model.compile(loss='categorical_crossentropy', optimizer=optimizer)

    return model


#単語から辞書IDを返す
def search_word_indices(word, word_to_id):
    if word in word_to_id:
        return word_to_id[word]
    else:
        return word_to_id['#OTHER']


#1行の文字列を学習データの形式に変換
def make_train_data(line, len_words, word_to_id):
    line=line.replace('\n','').replace('\r','')
    if line[0]==' ':
        line=line[1:]
    if line[-1]==' ':
        line=line[:-1]
    text_list=line.split(' ')
    f_sentences = []
    r_sentences = []
    next_words = []
    step=3
    len_text=len(text_list)
    if (len_text - maxlen_words*2 -1) > 0:
        for i in range(0, len_text - maxlen_words*2 -1, step):
            f_sentences.append(text_list[i: i + maxlen_words])
            r_sentences.append(text_list[i + maxlen_words+1: i + maxlen_words+1+maxlen_words][::-1]) #逆順のリスト
            next_words.append(text_list[i + maxlen_words])
        len_sent=len(f_sentences)

        f_X = np.zeros((len_sent, maxlen_words), dtype=np.int)
        r_X = np.zeros((len_sent, maxlen_words), dtype=np.int)
        Y = np.zeros((len_sent, len_words+1), dtype=np.bool)
        for i, sentence in enumerate(f_sentences):
            for t, word in enumerate(sentence):
                f_X[i, t] = search_word_indices(word, word_to_id)
            Y[i, search_word_indices(next_words[i],word_to_id)] = 1

        for i, sentence in enumerate(r_sentences):
            for t, word in enumerate(sentence):
                r_X[i, t] = search_word_indices(word, word_to_id)
    
    return f_X, r_X, Y


#loss, val_lossの追加更新
def conect_hist(list_loss, list_val_loss, new_history):
    list_loss.extend(new_history.history['loss'])
    list_val_loss.extend(new_history.history['val_loss'])


#1行10000単語までのファイルから1行ずつ1回学習する
#lossやval_lossは各行の学習結果の中央値を返す
def model_fit_once(train_path, my_model, len_words, word_to_id):
    tmp_loss_list=list()
    tmp_val_loss_list=list()

    with open(train_path) as f:
        for line in f:
            if line.count(' ')>maxlen_words*10:
                f_trainX, r_trainX, trainY = make_train_data(line, len_words, word_to_id)
                tmp_hist=my_model.fit([f_trainX,r_trainX], trainY, batch_size=128, epochs=1, validation_split=0.1)
                conect_hist(tmp_loss_list, tmp_val_loss_list, tmp_hist)
    
    loss=np.median(np.array(tmp_loss_list, dtype=np.float32))
    val_loss=np.median(np.array(tmp_val_loss_list, dtype=np.float32))    
    
    return loss, val_loss


#my_epochの数だけ学習をくりかえす
def model_fit_loop(train_path, my_model, len_words, word_to_id):
    list_loss=list()
    list_val_loss=list()
    for ep_i in range(my_epoch):
        print('\nEPOCH='+str(ep_i+1)+'/'+str(my_epoch)+'\n')
        loss, val_loss=model_fit_once(train_path, my_model,len_words, word_to_id)
        list_loss.append(loss)
        list_val_loss.append(val_loss)
        
        #モデルの保存
        dir_name=today_str+'Model_'+str(ep_i+1)
        os.mkdir(dir_name)

        model_json_str = my_model.to_json()
        file_model=dir_name+'/my_model'
        open(file_model+'.json', 'w').write(model_json_str)
        my_model.save_weights(file_model+'.h5')
        
        
    return list_loss, list_val_loss


# 損失の履歴をプロット
def plot_loss(list_loss, list_val_loss, title='model loss'):
    plt.plot(list_loss, color='blue', marker='o', label='loss')
    plt.plot(list_val_loss, color='green', marker='o', label='val_loss')
    plt.title(title)
    plt.xlabel('epoch')
    plt.ylabel('loss')
    plt.legend()
    plt.savefig(today_str+'loss_graph.png')
    #plt.show()は行うとプログラム中断されるからNG


#テストデータの前準備
def prepare_test(test_path, ch_path):
    
    th_len =maxlen_words/2    #テストの際の長さの閾値
    test_f_sentences = []
    test_r_sentences = []

    #テストデータへの読み込みと前処理
    #テストデータは学習データと異なり容量大きくないので一気に読み込んでいる
    #テストデータは1行1問で1行に<>が1つのみ
    test_file = open(test_path)
    test_data = test_file.read().lower().replace('\r','')
    test_file.close()

    ch_file= open(ch_path)
    ch_data= ch_file.read().lower().replace('\r','')
    ch_file.close()

    all_lines = test_data.split('\n')

    ch_lines = ch_data.split('\n')
    ans_list=[]
    ch_list=[]
    line_num=0

    for line in all_lines:
        tmp=re.split('<.+>', line)
        if(len(tmp)>1):
            test_f_tmp=re.sub(r'[^a-z ]', '', tmp[0])
            test_f_tmp = re.sub(r'[ ]+', ' ', test_f_tmp)
            test_r_tmp=re.sub(r'[^a-z ]', '', tmp[1])
            test_r_tmp = re.sub(r'[ ]+', ' ', test_r_tmp)
            test_f_line=test_f_tmp.split(' ')
            test_r_line=test_r_tmp.split(' ')
            if (len(test_f_line)>=th_len) and (len(test_r_line)>=th_len):
                if (len(test_f_line)>maxlen_words):
                    test_f_line=test_f_line[-1*maxlen_words:]
                if (len(test_r_line)>maxlen_words):
                    test_r_line=test_r_line[:maxlen_words]
                test_f_sentences.append(test_f_line)
                test_r_sentences.append(test_r_line[::-1])
                #テスト対象のデータの答えと選択肢をリストに格納
                tmp_ans=all_lines[line_num]
                tmp_ans=tmp_ans[tmp_ans.find('<')+1:tmp_ans.find('>')]
                ans_list.append(tmp_ans)
                tmp_ch=ch_lines[line_num]
                tmp_ch=tmp_ch[tmp_ch.find('<')+1:tmp_ch.find('>')]
                ch_list.append(tmp_ch)
                line_num+=1
                #テスト対象となるデータのみを出力
                with open(today_str+'testdata.txt', 'a') as data:
                    data.write(line+'\n')
    
    return test_f_sentences, test_r_sentences, ans_list, ch_list


#テストデータのベクトル化
def make_test_data(f_sent, r_sent, word_to_id):
    test_f_x = np.zeros((1, maxlen_words))
    test_r_x = np.zeros((1, maxlen_words))
    for t, word in enumerate(f_sent):
        tmp_index = search_word_indices(word, word_to_id)
        if(len(f_sent)<maxlen_words):
            test_f_x[0, t+maxlen_words-len(f_sent)] = tmp_index
        else:
            test_f_x[0, t] = tmp_index
    for t, word in enumerate(r_sent):
        tmp_index = search_word_indices(word, word_to_id)
        if(len(f_sent)<maxlen_words):
            test_r_x[0, t+maxlen_words-len(r_sent)] = tmp_index
        else:
            test_r_x[0, t] = tmp_index
    return test_f_x, test_r_x


#与えられた確率付き単語リストからランキング順に単語のみファイルへ書き込み
def print_rank(list1, fname, id_to_word):
    dict_A = dict((i,c) for i,c in enumerate(list1))
    list_B = sorted(dict_A.items(), key=lambda x: x[1], reverse=True)
    with open(fname, 'a') as file:
        for k,v in list_B:
            if k!=0:
                #idが0は存在しないので飛ばす
                str=id_to_word[k]+ ' ### '
                file.write(str)
        file.write('\n')


#単語とランクリストから単語の順位をstring型で返す
def word_to_rank(word, ra_list):
    str_num=''
    if word in ra_list:
        str_num=str(ra_list.index(word))
    else:
        #無いときは-1
        str_num='-1'

    return str_num


#TODOこの計算見直し
#確率で選んだ1語の正誤をファイル書き込み，正誤結果を返す
def calc_rank1word(ans, list_rank):
    pred=list_rank[0]
    rank_ans=word_to_rank(ans, list_rank)
    out=''
    with open(today_str+'rankOK.txt', 'a') as rOK:
        with open(today_str+'rankNG.txt', 'a') as rNG:
            out='pred= '+pred+'     '+'ans= '+ans+' : '+rank_ans+'\n'
            if pred==ans:
                rOK.write(out)
                OK_num=1
            else:
                rNG.write(out)
                OK_num=0
    return OK_num


#ランクリストと選択肢リストから，選択肢をランクリストの何番目に現れるか（順位）つきで並べた文字列を返す
#選択肢の語がランクリストにないときは-1
def search_rank(ra_list, ch_list):
    str_rank=''
    str_num=''
    k=0
    for x in ch_list:
        str_num=word_to_rank(x, ra_list)
        str_rank=str_rank+x+': '+str_num+' ### '
    #末尾のシャープとか消す
    k=len(str_rank)-5
    str_rank=str_rank[:k]

    return str_rank


#順位付き文字列と選択肢リストから最も順位の高い単語を返す
#どの語もランクリストにないときは#OTHERを返す
def serch_highest(str_rank, ch_list):
    tmp_list=str_rank.split(' ### ')
    num_list=[]
    flag=0
    word=''
    for x in tmp_list:
        num=int(x[x.index(': ')+2:])
        num_list.append(num)
    min=max(num_list)+10    #この10に特に意味はない．単に大きい数字にしたいだけ
    min_ct=0
    ct=0
    for i in num_list:
        if (i>=0) and (min>i):
            flag=1
            min=i
            min_ct=ct
        ct+=1

    if flag==0:
        word='#OTHER'
    else:
        word=ch_list[min_ct]

    return word


#確率で選択肢から選んだ際の正誤をファイル書き込み，正誤結果を返す
def calc_rank4choices(choices, ans, list_rank):
    #まず選択肢をリストへ
    choi_list=choices.split(' ### ')
    out=search_rank(list_rank, choi_list)
    pred=serch_highest(out, choi_list)

    with open(today_str+'choicesOK.txt', 'a') as cOK:
        with open(today_str+'choicesNG.txt', 'a') as cNG:
            out=out+'\n'
            if pred==ans:
                cOK.write(out)
                OK_num=1
            else:
                cNG.write(out)
                OK_num=0
    return OK_num


#正解率の計算結果を文字列で返す
def calc_acc(ans_list, ch_list, rank_file):
    sent_i=0
    rankOK=0
    choiOK=0

    with open(rank_file,'r') as rank:
        for line in rank:
            rank_line=line.replace('\n','').replace('\r','')
            rank_list=rank_line.split(' ### ')
            rankOK+=calc_rank1word(ans_list[sent_i], rank_list)
            choiOK+=calc_rank4choices(ch_list[sent_i], ans_list[sent_i], rank_list)
            sent_i+=1

    rank_acc=1.0*rankOK/sent_i
    choi_acc=1.0*choiOK/sent_i

    rankNG=sent_i - rankOK
    choiNG=sent_i - choiOK

    rank_result='rank: '+str(rank_acc)+' ( OK: '+str(rankOK)+'   NG: '+str(rankNG)+' )\n'
    choi_result='choi: '+str(choi_acc)+' ( OK: '+str(choiOK)+'   NG: '+str(choiNG)+' )\n'

    result=rank_result+choi_result
    
    return result


#テスト
def model_test(model, test_path, ch_path, word_to_id):
    #テストデータの前準備
    f_sent, r_sent, ans_list, ch_list = prepare_test(test_path, ch_path)
    sent_num=len(f_sent)
    #テストの実行
    for i in range(sent_num):
        f_testX, r_testX = make_test_data(f_sent[i], r_sent[i], word_to_id)
        preds = min_model.predict([f_testX,r_testX], verbose=0)[0]#    TODO この[0]の意味確認
        rank_file=today_str+'rank.txt'
        print_rank(preds, rank_file, id_to_word)
    #正解率の計算，ファイル出力
    result_str=calc_acc(ans_list, ch_list, rank_file)

    return result_str


#model.summary()のファイル出力用
def myprint(s):
    with open(today_str+'model_summary.txt','a') as f:
        print(s, file=f)





#----- いわゆるmain部みたいなの -----

# 0.いろいろ前準備
#開始時刻のプリント
start_time=print_time('all start')
start_time_str = start_time.strftime('%Y_%m_%d_%H%M')

#モデルとか結果とかを格納するディレクトリの作成
today_str=start_time_str+'epoch'+str(my_epoch)
if os.path.exists(today_str)==False:
    os.mkdir(today_str)
today_str='./'+today_str+'/'

#学習データの候補
train_big='../corpus/WikiSentWithEndMark1.txt'   # 約5.8GB，約2000万行
train_enwiki='../corpus/enwiki.txt'   # 約24GB，1行のみ，約435億単語(920万5021種類)
train_mid='../corpus/miniWiki_tmp8.txt'   # 約1.5MB，約5000行
train_small='../corpus/nietzsche.txt'   # 約600KB，約1万行
train_test='../corpus/mini_text8.txt'

train_text8='../corpus/text8.txt'   # 約95MB 1行のみ, 約1700万単語(25万3854種類)  http://mattmahoney.net/dc/text8.zip



# 1.学習データの前処理など
tmp_path = train_test        #使用する学習データ
print('Loading  '+tmp_path)
train_path=preprocess(tmp_path)



# 2.fasttextのロードと辞書の作成
'''
https://github.com/facebookresearch/fastText
このfastextを事前に実行しておき，その結果を利用
'''
ft_path='../../FastText/fastText-0.1.0/fasttext'

#ベクトルファイルの候補
vec_enwiki='../../FastText/Model/enwiki_dim'+str(vec_size)+'_minC0.vec'
bin_enwiki='../../FastText/Model/enwiki_dim'+str(vec_size)+'_minC0.bin'
vec_text8='../../FastText/Model/text8_dim'+str(vec_size)+'_minC0.vec'
bin_text8='../../FastText/Model/text8_dim'+str(vec_size)+'_minC0.bin'

vec_small='../../FastText/Model/nietzsche_dim'+str(vec_size)+'_minC0.vec'
bin_small='../../FastText/Model/nietzsche_dim'+str(vec_size)+'_minC0.bin'

#実際に使うもの
vec_path=vec_text8
bin_path=bin_text8

len_words, word_to_id, id_to_word, vec_dict=vec_to_dict(vec_path)

#embeddingで用いる，単語から行列への変換行列
embedding_matrix = np.zeros((len_words+1, vec_size))
for i in range(len_words):
    if i!=0:
        #IDが0の単語が存在しないので0は飛ばす
        embedding_matrix[i] = get_ft_vec(id_to_word[i], vec_dict, ft_path, bin_path)
        

end_data=print_time('prepare data and fasttext end')



# 3.モデルの定義
my_model=build_model(len_words, embedding_matrix)



# 4.モデルの学習
loss, val_loss=model_fit_loop(train_path, my_model, len_words, word_to_id)
plot_loss(loss, val_loss)

end_train=print_time('train end')



# 5.val_loss最小モデルのロード
min_i=np.array(val_loss).argmin()

min_model_file=today_str+'Model_'+str(min_i+1)+'/my_model.json'
min_weight_file=today_str+'Model_'+str(min_i+1)+'/my_model.h5'
print('Loading  '+min_model_file)

json_string = open(min_model_file).read()
min_model = model_from_json(json_string)
min_model.load_weights(min_weight_file)
optimizer = RMSprop()
min_model.compile(loss='categorical_crossentropy', optimizer=optimizer)

plot_model(min_model, to_file=today_str+'model.png', show_shapes=True)
min_model.summary(print_fn=myprint)

end_load=print_time('Load min_model end')



# 6.テストの実行
test_path = '../corpus/tmp_testdata_after.txt'     #答えつきテストデータ
ch_path= '../corpus/tmp_choices_after.txt'     #選択肢つきテストデータ

result=model_test(min_model, test_path, ch_path, word_to_id)
print('\n'+result)

with open(today_str+'keyerror_words.txt', 'w') as f_key:
    for word in KeyError_set:
        f_key.write(word+'\n')


end_test=print_time('test end')



#7.実行結果まとめのファイル書き込み
#下記内容をファイルにまとめて出力
'''
・実行したプログラム名
・実施日時（開始時刻）
・読み込んだ学習データ
・単語数
・全学習回数
・val_loss最小の学習回数

・テスト結果

・modelの概要

・学習データの前処理，辞書の作成ににかかった時間
・fasttextのロードとembedding_matrixの作成にかかった時間
・学習にかかった時間（ベクトル化も含む）
・val_loss最小モデルのロードにかかった時間
・テストにかかった時間（ベクトル化，正解率とかも含む）
・全合計かかった時間
'''

#実行結果のあれこれをファイル書き込み

with open(today_str+'summary.txt', 'a') as f:
    f.write('Result of '+os.path.basename(__file__)+'\n\n')
    
    f.write('start_time = '+ start_time_str+'\n')
    f.write('epoch = '+str(my_epoch)+'\n')
    f.write('train_data = '+ train_path+'\n')
    f.write('kind of words ='+str(len_words)+'\n')
    f.write('min_model = '+ min_model_file+'\n\n')

    f.write('result\n'+ result+'\n')

    f.write('TIME prepare data and fasttext= '+ str(end_data-start_time)+'\n')
    f.write('TIME train = '+ str(end_train-end_data)+'\n')
    f.write('TIME load min_model = '+ str(end_load-end_train)+'\n')
    f.write('TIME test = '+ str(end_test-end_load)+'\n\n')

    end_time=print_time('all end')
    f.write('TIME total = '+ str(end_time-start_time)+'\n')

